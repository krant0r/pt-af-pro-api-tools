from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger

from .auth import TenantAuth, TokenManager
from .config import config
from .tenants import fetch_tenants
from .snapshots import _slugify


def _tenant_subdir(base: Path, tenant: Dict[str, Any]) -> Path:
    name = _slugify(str(tenant.get("name") or tenant.get("displayName") or tenant["id"]))
    tenant_id = tenant.get("id", "unknown")
    subdir = base / f"{name}_{tenant_id}"
    subdir.mkdir(parents=True, exist_ok=True)
    return subdir


def _normalize_items(data: Any) -> List[Dict[str, Any]]:
    """
    PTAF может отдавать:
      - список объектов
      - {"items": [..]}
    Делаем единый формат: List[dict].
    """
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        return data["items"]
    if isinstance(data, list):
        return data
    raise RuntimeError(f"Unsupported list response type: {type(data)}")


# ---------------------------------------------------------------------------
# EXPORT
# ---------------------------------------------------------------------------


async def export_rules_for_tenant(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant: Dict[str, Any],
) -> List[Path]:
    tenant_id = str(tenant.get("id"))
    subdir = _tenant_subdir(config.RULES_DIR, tenant)

    url = f"{config.AF_URL}{config.RULES_ENDPOINT}"
    logger.info(f"[tenant={tenant_id}] Exporting rules from {url}")

    auth = TenantAuth(tm, tenant_id=tenant_id)
    r = await client.get(url, auth=auth)
    r.raise_for_status()

    items = _normalize_items(r.json())
    created: List[Path] = []

    for rule in items:
        rule_id = rule.get("id") or rule.get("name") or "rule"
        fname = subdir / f"{_slugify(str(rule_id))}.rule.json"
        fname.write_text(
            json.dumps(rule, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created.append(fname)

    logger.success(
        f"[tenant={tenant_id}] Exported {len(created)} rule objects to {subdir}"
    )
    return created


async def export_actions_for_tenant(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant: Dict[str, Any],
) -> List[Path]:
    tenant_id = str(tenant.get("id"))
    subdir = _tenant_subdir(config.ACTIONS_DIR, tenant)

    url = f"{config.AF_URL}{config.ACTIONS_ENDPOINT}"
    logger.info(f"[tenant={tenant_id}] Exporting actions from {url}")

    auth = TenantAuth(tm, tenant_id=tenant_id)
    r = await client.get(url, auth=auth)
    r.raise_for_status()

    items = _normalize_items(r.json())
    created: List[Path] = []

    for action in items:
        act_id = action.get("id") or action.get("name") or "action"
        fname = subdir / f"{_slugify(str(act_id))}.action.json"
        fname.write_text(
            json.dumps(action, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created.append(fname)

    logger.success(
        f"[tenant={tenant_id}] Exported {len(created)} action objects to {subdir}"
    )
    return created


async def export_rules_for_all_tenants(tm: TokenManager) -> List[Path]:
    """
    Массовый экспорт правил для всех тенантов в config.RULES_DIR.
    """
    created: List[Path] = []
    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        tenants = await fetch_tenants(client, tm)
        if not tenants:
            logger.warning("No tenants returned by API (rules export)")
            return []

        for tenant in tenants:
            created.extend(await export_rules_for_tenant(client, tm, tenant))

    return created


async def export_actions_for_all_tenants(tm: TokenManager) -> Tuple[List[Path], List[str]]:
    """
    Массовый экспорт actions для всех тенантов в config.ACTIONS_DIR.

    Возвращает список созданных файлов и список ошибок, которые нужно показать
    пользователю (например, при сбое запроса к general-tenant).
    """
    created: List[Path] = []
    errors: List[str] = []
    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        tenants = await fetch_tenants(client, tm)
        if not tenants:
            logger.warning("No tenants returned by API (actions export)")
            return [], []

        for tenant in tenants:
            tenant_id = str(tenant.get("id"))
            try:
                created.extend(await export_actions_for_tenant(client, tm, tenant))
            except httpx.HTTPStatusError as exc:
                if tenant_id == "00000000-0000-0000-0000-000000000000":
                    msg = (
                        f"[tenant={tenant_id}] Failed to export actions: "
                        f"{exc}"
                    )
                    logger.error(msg)
                    errors.append(msg)
                    continue
                raise

    return created, errors


# ---------------------------------------------------------------------------
# IMPORT
# ---------------------------------------------------------------------------


async def import_rule_payload(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Импорт ОДНОГО правила (payload уже dict).
    По умолчанию POST на RULES_ENDPOINT.
    Если PTAF потребует другой метод/URL — поправишь в конфиге/коде.
    """
    url = f"{config.AF_URL}{config.RULES_ENDPOINT}"
    auth = TenantAuth(tm, tenant_id=tenant_id)
    r = await client.post(url, json=payload, auth=auth)
    r.raise_for_status()
    logger.info(f"[tenant={tenant_id}] Rule imported via POST {url}")
    return r.json()


async def import_action_payload(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    url = f"{config.AF_URL}{config.ACTIONS_ENDPOINT}"
    auth = TenantAuth(tm, tenant_id=tenant_id)
    r = await client.post(url, json=payload, auth=auth)
    r.raise_for_status()
    logger.info(f"[tenant={tenant_id}] Action imported via POST {url}")
    return r.json()


def load_json_file(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _tenant_label_from_dir(dir_name: str) -> Tuple[str, Optional[str]]:
    """
    Возвращает человекочитаемое имя тенанта и id (если он есть в имени каталога).
    Каталоги экспорта имеют вид <slug>_<id>.
    """

    if "_" in dir_name:
        base, _, tenant_id = dir_name.rpartition("_")
    else:
        base, tenant_id = dir_name, None

    friendly = base.replace("-", " ").replace("_", " ").strip() or dir_name
    return friendly, tenant_id


def _normalize_label(label: str) -> str:
    return label.replace("-", " ").replace("_", " ").strip().lower()


def _read_display_name(path: Path, suffix: str) -> str:
    """
    Try to extract human-friendly name from exported JSON payload.

    Falls back to the filename (without suffix) if JSON is invalid or
    doesn't contain a "name" field.
    """

    try:
        data = load_json_file(path)
        name = data.get("name")
        if name:
            return str(name)
    except Exception:
        logger.debug(f"Failed to read name from {path}")

    stem = path.name
    extended_suffix = f".{suffix}.json"
    if stem.endswith(extended_suffix):
        stem = stem[: -len(extended_suffix)]
    elif stem.endswith(path.suffix):
        stem = path.stem
    return stem


def list_local_exports(base: Path, suffix: str) -> List[Dict[str, Any]]:
    """
    Собирает список экспортированных файлов указанного типа (rules/actions).
    Возвращает структуры вида:
    {"tenant_name": "...", "tenant_dir": "...", "tenant_id": "...", "files": [{filename, display_name}]}
    """

    results: List[Dict[str, Any]] = []
    for subdir in sorted(base.iterdir()):
        if not subdir.is_dir():
            continue

        tenant_name, tenant_id = _tenant_label_from_dir(subdir.name)
        files_meta: List[Dict[str, str]] = []

        for path in sorted(subdir.glob(f"*.{suffix}.json")):
            if not path.is_file():
                continue
            files_meta.append(
                {
                    "filename": path.name,
                    "display_name": _read_display_name(path, suffix),
                }
            )

        if not files_meta:
            continue

        results.append(
            {
                "tenant_name": tenant_name,
                "tenant_dir": subdir.name,
                "tenant_id": tenant_id,
                "files": files_meta,
            }
        )

    return results


def load_local_payload(
    base: Path, tenant_name: str, filename: str, suffix: str
) -> Dict[str, Any]:
    """
    Читает JSON-файл из локального каталога экспорта по названию тенанта.
    Поддерживает только файлы с расширением .<suffix>.json.
    """

    if not filename.endswith(f".{suffix}.json"):
        raise ValueError(
            f"Filename must end with .{suffix}.json (got {filename!r})"
        )

    normalized_target = _normalize_label(tenant_name)

    for subdir in base.iterdir():
        if not subdir.is_dir():
            continue

        friendly, _ = _tenant_label_from_dir(subdir.name)
        if _normalize_label(friendly) != normalized_target and _normalize_label(
            subdir.name
        ) != normalized_target:
            continue

        candidate = subdir / filename
        if candidate.is_file():
            return load_json_file(candidate)

    raise FileNotFoundError(
        f"File {filename} for tenant {tenant_name!r} not found in {base}"
    )
