from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger

from .auth import TenantAuth, TokenManager
from .config import config
from .tenants import fetch_tenants
from .snapshots import _slugify, get_snapshot_from_cache


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
    """
    Экспорт правил тенанта. Сохраняет во временный файл и обновляет RAM кэш.
    """
    tenant_id = str(tenant.get("id"))
    
    url = f"{config.AF_URL}{config.RULES_ENDPOINT}"
    logger.info(f"[tenant={tenant_id}] Exporting rules from {url}")

    auth = TenantAuth(tm, tenant_id=tenant_id)
    try:
        r = await client.get(url, auth=auth)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"[tenant={tenant_id}] Failed to export rules: {e}")
        return []

    items = _normalize_items(r.json())
    
    # Сохраняем во временный файл
    name = _slugify(str(tenant.get("name") or tenant.get("displayName") or tenant_id))
    subdir = config.RULES_DIR / f"{name}_{tenant_id}"
    subdir.mkdir(parents=True, exist_ok=True)
    
    created: List[Path] = []
    for rule in items:
        rule_id = rule.get("id") or rule.get("name") or "rule"
        fname = subdir / f"{_slugify(str(rule_id))}.rule.json"
        fname.write_text(
            json.dumps(rule, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created.append(fname)

    logger.success(f"[tenant={tenant_id}] Exported {len(created)} rule objects to {subdir}")
    return created


async def export_actions_for_tenant(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant: Dict[str, Any],
) -> List[Path]:
    """
    Экспорт действий тенанта. Сохраняет во временный файл.
    """
    tenant_id = str(tenant.get("id"))
    
    url = f"{config.AF_URL}{config.ACTIONS_ENDPOINT}"
    logger.info(f"[tenant={tenant_id}] Exporting actions from {url}")

    auth = TenantAuth(tm, tenant_id=tenant_id)
    try:
        r = await client.get(url, auth=auth)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"[tenant={tenant_id}] Failed to export actions: {e}")
        return []

    items = _normalize_items(r.json())
    
    # Сохраняем во временный файл
    name = _slugify(str(tenant.get("name") or tenant.get("displayName") or tenant_id))
    subdir = config.ACTIONS_DIR / f"{name}_{tenant_id}"
    subdir.mkdir(parents=True, exist_ok=True)
    
    created: List[Path] = []
    for action in items:
        act_id = action.get("id") or action.get("name") or "action"
        fname = subdir / f"{_slugify(str(act_id))}.action.json"
        fname.write_text(
            json.dumps(action, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        created.append(fname)

    logger.success(f"[tenant={tenant_id}] Exported {len(created)} action objects to {subdir}")
    return created


async def export_actions_for_all_tenants(tm: TokenManager) -> List[Path]:
    """Экспорт действий для всех тенантов."""
    created: List[Path] = []
    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        tenants = await fetch_tenants(client, tm)
        if not tenants:
            logger.warning("No tenants returned by API (actions export)")
            return []

        for tenant in tenants:
            files = await export_actions_for_tenant(client, tm, tenant)
            created.extend(files)

    return created


async def export_rules_for_all_tenants(tm: TokenManager) -> List[Path]:
    """Экспорт правил для всех тенантов."""
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
            files = await export_rules_for_tenant(client, tm, tenant)
            created.extend(files)

    return created


# ---------------------------------------------------------------------------
# IMPORT
# ---------------------------------------------------------------------------


async def import_rule_from_snapshot(
    client: httpx.AsyncClient,
    tm: TokenManager,
    target_tenant_id: str,
    source_tenant_id: str,
    rule_name: str,
) -> Dict[str, Any]:
    """
    Импорт пользовательского правила из снапшота исходного тенанта (RAM кэш).
    """
    snapshot = get_snapshot_from_cache(source_tenant_id)
    if not snapshot:
        return {"error": f"No snapshot cached for source tenant {source_tenant_id}"}
    
    user_rules = snapshot.get("user_rules", [])
    if not isinstance(user_rules, list):
        return {"error": "Invalid user_rules format in snapshot"}
    
    selected_rule = None
    for rule in user_rules:
        if rule.get("name") == rule_name:
            selected_rule = rule
            break
    
    if not selected_rule:
        return {"error": f"Rule '{rule_name}' not found in snapshot of tenant {source_tenant_id}"}
    
    url = f"{config.AF_URL}{config.RULES_ENDPOINT}"
    auth = TenantAuth(tm, tenant_id=target_tenant_id)
    r = await client.post(url, json=selected_rule, auth=auth)
    r.raise_for_status()
    logger.info(f"[tenant={target_tenant_id}] Rule '{rule_name}' imported from snapshot of {source_tenant_id}")
    return r.json()


async def import_rule_payload(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Импорт ОДНОГО правила (payload уже dict).
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
    """Импорт ОДНОГО действия."""
    url = f"{config.AF_URL}{config.ACTIONS_ENDPOINT}"
    auth = TenantAuth(tm, tenant_id=tenant_id)
    r = await client.post(url, json=payload, auth=auth)
    r.raise_for_status()
    logger.info(f"[tenant={tenant_id}] Action imported via POST {url}")
    return r.json()


def _tenant_label_from_dir(dir_name: str) -> Tuple[str, Optional[str]]:
    """
    Возвращает человекочитаемое имя тенанта и id.
    """
    if "_" in dir_name:
        base, _, tenant_id = dir_name.rpartition("_")
    else:
        base, tenant_id = dir_name, None

    friendly = base.replace("-", " ").replace("_", " ").strip() or dir_name
    return friendly, tenant_id


def list_local_exports(base: Path, suffix: str) -> List[Dict[str, Any]]:
    """
    Собирает список экспортированных файлов из временной директории.
    """
    results: List[Dict[str, Any]] = []
    if not base.exists():
        return results
    
    for subdir in sorted(base.iterdir()):
        if not subdir.is_dir():
            continue

        tenant_name, tenant_id = _tenant_label_from_dir(subdir.name)
        files_meta: List[Dict[str, str]] = []

        for path in sorted(subdir.glob(f"*.{suffix}.json")):
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                name = data.get("name", path.stem)
            except Exception:
                name = path.stem
            files_meta.append(
                {
                    "filename": path.name,
                    "display_name": str(name),
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
    Читает JSON-файл из временной директории.
    """
    if not filename.endswith(f".{suffix}.json"):
        raise ValueError(
            f"Filename must end with .{suffix}.json (got {filename!r})"
        )

    if not base.exists():
        raise FileNotFoundError(f"Directory {base} not found")

    for subdir in base.iterdir():
        if not subdir.is_dir():
            continue

        friendly, _ = _tenant_label_from_dir(subdir.name)
        if friendly.lower() != tenant_name.lower() and subdir.name.lower() != tenant_name.lower():
            continue

        candidate = subdir / filename
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))

    raise FileNotFoundError(
        f"File {filename} for tenant {tenant_name!r} not found in {base}"
    )
