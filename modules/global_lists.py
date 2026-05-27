from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import httpx
from loguru import logger

from .auth import TokenManager, TenantAuth
from .config import config
from .tenants import fetch_tenants
from .rules_actions import _tenant_subdir, _normalize_items


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

    data = r.json()
    items = _normalize_items(data)  # поддержка {"items": [...]} или прямого списка
    created: List[Path] = []

    for gl in items:
        gl_id = gl.get("id") or gl.get("name") or "global_list"
        # Используем slugify для безопасного имени файла
        from .snapshots import _slugify
        fname = subdir / f"{_slugify(str(gl_id))}.globallist.json"
        fname.write_text(
            json.dumps(gl, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created.append(fname)

    logger.success(f"[tenant={tenant_id}] Exported {len(created)} global lists to {subdir}")
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