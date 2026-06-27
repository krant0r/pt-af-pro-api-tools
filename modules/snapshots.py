from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

import httpx
from loguru import logger

from .auth import TokenManager, TenantAuth
from .config import config
from .tenants import fetch_tenants


# Глобальный кэш снапшотов в RAM: tenant_id -> snapshot_data
_snapshot_cache: Dict[str, Dict[str, Any]] = {}


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "tenant"


def clear_snapshot_cache() -> None:
    """Очистить кэш снапшотов."""
    global _snapshot_cache
    _snapshot_cache = {}
    logger.info("Snapshot cache cleared")


def get_snapshot_cache() -> Dict[str, Dict[str, Any]]:
    """Вернуть кэш снапшотов."""
    return _snapshot_cache


def collect_snapshot_summary_from_cache() -> Dict[str, Any]:
    """Собрать summary из RAM кэша снапшотов."""
    applications: set[str] = set()
    hosts: set[str] = set()
    tenant_hosts: list[dict[str, Any]] = []
    
    for tenant_id, data in _snapshot_cache.items():
        if not isinstance(data, dict):
            continue
        
        # Извлекаем имя тенанта из различных возможных полей
        tenant_name = (
            data.get("tenantName") 
            or data.get("tenant_name") 
            or (data.get("tenant") or {}).get("name")
            or (data.get("tenant") or {}).get("displayName")
            or tenant_id
        )
        tenant_hosts_set: set[str] = set()
        
        apps = data.get("applications")
        if isinstance(apps, list):
            for app in apps:
                if not isinstance(app, dict):
                    continue
                name = app.get("name")
                if isinstance(name, str) and name.strip():
                    applications.add(name.strip())
                app_hosts = app.get("hosts")
                if isinstance(app_hosts, list):
                    for host in app_hosts:
                        if isinstance(host, str) and host.strip():
                            cleaned = host.strip()
                            hosts.add(cleaned)
                            tenant_hosts_set.add(cleaned)
        
        tenant_hosts.append(
            {"tenant_name": tenant_name, "tenant_id": tenant_id, "hosts": sorted(tenant_hosts_set)}
        )
    
    return {
        "snapshot_files": len(_snapshot_cache),
        "applications": sorted(applications),
        "hosts": sorted(hosts),
        "tenant_hosts": tenant_hosts,
    }


async def fetch_all_snapshots(tm: TokenManager) -> tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Получить снапшоты всех тенантов и сохранить в RAM кэш.
    Возвращает кортеж: (dict tenant_id -> snapshot_data, list ошибок)
    """
    global _snapshot_cache
    _snapshot_cache = {}
    errors = []
    
    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        token = await tm.ensure_base_token(client)
        if not token:
            raise RuntimeError("Unable to obtain base access token (check credentials)")

        tenants = await fetch_tenants(client, tm)
        if not tenants:
            logger.warning("No tenants returned by API")
            return {}, []

        logger.info(f"Fetching snapshots for {len(tenants)} tenants")

        for tenant in tenants:
            tenant_id = str(tenant.get("id"))
            tenant_name = tenant.get("name") or tenant.get("displayName") or tenant_id
            url = f"{config.AF_URL}{config.SNAPSHOT_ENDPOINT}"
            auth = TenantAuth(tm, tenant_id=tenant_id)
            try:
                r = await client.get(url, auth=auth)
                r.raise_for_status()
                data = r.json()
                _snapshot_cache[tenant_id] = data
                logger.success(f"[tenant={tenant_id}] Snapshot fetched and cached")
            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
                logger.error(f"[tenant={tenant_id}] Snapshot fetch failed: {error_msg}")
                errors.append({
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_name,
                    "error": error_msg,
                    "status_code": e.response.status_code,
                })
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[tenant={tenant_id}] Snapshot fetch failed: {error_msg}")
                errors.append({
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_name,
                    "error": error_msg,
                })

    logger.info(f"Total snapshots cached: {len(_snapshot_cache)}")
    if errors:
        logger.warning(f"Total errors: {len(errors)}")
    return _snapshot_cache, errors


async def export_snapshot_for_tenant(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant: Dict[str, Any],
) -> Optional[Path]:
    """
    Получить снапшот тенанта и сохранить во временный файл.
    Также обновляет RAM кэш.
    """
    tenant_id = str(tenant.get("id"))
    if not tenant_id:
        logger.error(f"Tenant object has no 'id': {tenant}")
        return None

    url = f"{config.AF_URL}{config.SNAPSHOT_ENDPOINT}"
    logger.info(f"[tenant={tenant_id}] Exporting snapshot from {url}")

    auth = TenantAuth(tm, tenant_id=tenant_id)
    try:
        r = await client.get(url, auth=auth)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"[tenant={tenant_id}] Snapshot export failed: {e}")
        return None

    data = r.json()
    _snapshot_cache[tenant_id] = data
    
    # Сохраняем во временный файл
    name = _slugify(str(tenant.get("name") or tenant.get("displayName") or tenant_id))
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fname = config.SNAPSHOTS_DIR / f"{ts}_{name}_{tenant_id}.snapshot.json"
    fname.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.success(f"[tenant={tenant_id}] Snapshot written to {fname}")
    return fname


async def export_all_tenant_snapshots(tm: TokenManager) -> List[Path]:
    """
    Получить снапшоты всех тенантов, сохранить в RAM и временные файлы.
    Возвращает список путей к файлам.
    """
    created_files: List[Path] = []

    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        token = await tm.ensure_base_token(client)
        if not token:
            raise RuntimeError("Unable to obtain base access token (check credentials)")

        tenants = await fetch_tenants(client, tm)
        if not tenants:
            logger.warning("No tenants returned by API")
            return []

        logger.info(f"Exporting snapshots for {len(tenants)} tenants")

        for tenant in tenants:
            path = await export_snapshot_for_tenant(client, tm, tenant)
            if path:
                created_files.append(path)

    logger.info(f"Total snapshots written: {len(created_files)}")
    return created_files


def get_snapshot_from_cache(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Вернуть снапшот тенанта из RAM кэша."""
    return _snapshot_cache.get(tenant_id)


def get_latest_snapshot_path(tenant_id: str) -> Optional[Path]:
    """
    Вернуть путь к файлу снапшота во временной директории.
    Используется для совместимости со старым кодом импорта.
    """
    if not config.SNAPSHOTS_DIR.exists():
        return None
    latest: Optional[tuple[Path, datetime]] = None
    for path in config.SNAPSHOTS_DIR.glob("*.snapshot.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            tid = data.get("meta", {}).get("tenant", {}).get("id")
            if tid != tenant_id:
                continue
            ts = datetime.utcnow()
            if latest is None or ts > latest[1]:
                latest = (path, ts)
        except Exception:
            continue
    return latest[0] if latest else None


def latest_snapshot_per_tenant() -> Dict[str, str]:
    """
    Returns mapping tenant_id -> latest snapshot timestamp (ISO string, UTC).
    Для обратной совместимости.
    """
    latest: Dict[str, datetime] = {}
    if not config.SNAPSHOTS_DIR.exists():
        return {}
    for path in config.SNAPSHOTS_DIR.glob("*.snapshot.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            tenant_id = data.get("meta", {}).get("tenant", {}).get("id")
            if not tenant_id:
                continue
            ts = datetime.utcnow()
            current = latest.get(tenant_id)
            if not current or ts > current:
                latest[tenant_id] = ts
        except Exception:
            continue
    return {
        tid: dt.replace(microsecond=0).isoformat() + "Z" for tid, dt in latest.items()
    }


def get_applications_from_snapshot(tenant_id: str) -> List[Dict[str, Any]]:
    """Вернуть список приложений из снапшота тенанта в RAM кэше."""
    data = _snapshot_cache.get(tenant_id)
    if not data:
        return []
    apps = data.get("applications")
    if isinstance(apps, list):
        return apps
    return []


def get_user_rules_from_snapshot(tenant_id: str) -> List[Dict[str, Any]]:
    """Вернуть список пользовательских правил из снапшота тенанта в RAM кэше."""
    data = _snapshot_cache.get(tenant_id)
    if not data:
        return []
    user_rules = data.get("user_rules")
    if isinstance(user_rules, list):
        return [{"name": rule.get("name", "Unnamed")} for rule in user_rules]
    return []


def get_user_actions_from_snapshot(tenant_id: str) -> List[Dict[str, Any]]:
    """Вернуть список пользовательских действий из снапшота тенанта в RAM кэше."""
    data = _snapshot_cache.get(tenant_id)
    if not data:
        return []
    user_actions = data.get("user_actions")
    if isinstance(user_actions, list):
        return user_actions
    return []


def get_global_lists_from_snapshot(tenant_id: str) -> List[Dict[str, Any]]:
    """Вернуть список глобальных списков из снапшота тенанта в RAM кэше."""
    data = _snapshot_cache.get(tenant_id)
    if not data:
        return []
    global_lists = data.get("global_lists")
    if isinstance(global_lists, list):
        return global_lists
    return []
