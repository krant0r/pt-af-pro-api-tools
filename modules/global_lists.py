from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote

import httpx
from loguru import logger

from .auth import TokenManager, TenantAuth
from .config import config
from .tenants import fetch_tenants
from .rules_actions import _tenant_subdir, _normalize_items
from .snapshots import _slugify   # <-- добавлен импорт


def _extract_filename_from_cd(content_disposition: str) -> str | None:
    """
    Извлекает имя файла из заголовка Content-Disposition.
    Поддерживает формы:
      - filename*=UTF-8''encoded_name.txt
      - filename="quoted name.txt"
      - filename=plainname.txt
    """
    # RFC 5987: filename*=UTF-8''value
    match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition)
    if match:
        return unquote(match.group(1))
    # Обычный filename в кавычках или без
    match = re.search(r'filename="([^"]+)"', content_disposition)
    if not match:
        match = re.search(r"filename=([^;]+)", content_disposition)
    if match:
        return match.group(1).strip('"')
    return None


async def export_global_lists_for_tenant(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant: Dict[str, Any],
) -> List[Path]:
    """
    Экспорт всех глобальных списков для указанного тенанта.
    Каждый список сохраняется в отдельный JSON-файл внутри
    <GLOBAL_LISTS_DIR>/<tenant_slug>_<tenant_id>/.
    """
    tenant_id = str(tenant.get("id"))
    subdir = _tenant_subdir(config.GLOBAL_LISTS_DIR, tenant)

    url = f"{config.AF_URL}{config.GLOBAL_LISTS_ENDPOINT}"
    logger.info(f"[tenant={tenant_id}] Exporting global lists from {url}")

    auth = TenantAuth(tm, tenant_id=tenant_id)
    try:
        r = await client.get(url, auth=auth)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"[tenant={tenant_id}] Failed to export global lists: {e}")
        return []

    items = _normalize_items(r.json())
    created: List[Path] = []

    for gl in items:
        gl_id = gl.get("id") or gl.get("name") or "global_list"

        # 1. Сохраняем JSON-конфигурацию списка
        fname_json = subdir / f"{_slugify(str(gl_id))}.globallist.json"
        fname_json.write_text(
            json.dumps(gl, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created.append(fname_json)

        # 2. Запрашиваем и сохраняем содержимое файла списка
        base_endpoint = config.GLOBAL_LISTS_ENDPOINT.rstrip('/')
        file_url = f"{config.AF_URL}{base_endpoint}/{gl_id}/file"
        logger.debug(f"[tenant={tenant_id}] Fetching global list file from {file_url}")
        # Используем тот же клиент, повторно создавать auth не нужно
        try:
            resp_file = await client.get(file_url, auth=auth)
            resp_file.raise_for_status()
        except Exception as e:
            logger.error(f"[tenant={tenant_id}] Failed to fetch file for list {gl_id}: {e}")
            continue

        # Определяем имя файла для сохранения
        cd_header = resp_file.headers.get("content-disposition")
        filename = None
        if cd_header:
            filename = _extract_filename_from_cd(cd_header)
        if not filename:
            # Запасной вариант: slug_id.txt
            filename = f"{_slugify(str(gl_id))}.txt"
        # Убираем возможные разделители путей
        filename = filename.replace("/", "_")
        file_path = subdir / filename

        # Сохраняем содержимое (текстовое, но пишем байты как есть)
        file_path.write_bytes(resp_file.content)
        logger.debug(f"[tenant={tenant_id}] Saved global list file to {file_path}")
        created.append(file_path)

        logger.success(f"[tenant={tenant_id}] Exported global list {gl_id} (config + file)")

    logger.success(f"[tenant={tenant_id}] Exported {len(created)} objects (configs + files) to {subdir}")
    return created


async def export_global_lists_for_all_tenants(tm: TokenManager) -> List[Path]:
    """
    Экспорт глобальных списков для всех доступных тенантов.
    """
    created: List[Path] = []
    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        tenants = await fetch_tenants(client, tm)
        if not tenants:
            logger.warning("No tenants returned by API (global lists export)")
            return []

        for tenant in tenants:
            files = await export_global_lists_for_tenant(client, tm, tenant)
            created.extend(files)

    return created