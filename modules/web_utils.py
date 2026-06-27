from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx
from loguru import logger

from .auth import TokenManager, TenantAuth, AuthenticationError
from .config import config
from .tenants import fetch_tenants
from .snapshots import latest_snapshot_per_tenant, get_applications_from_snapshot


async def fetch_tenants_with_snapshots() -> List[Dict[str, Any]]:
    """Загружает список тенантов и добавляет дату последнего снапшота."""
    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        tm = TokenManager()
        try:
            tenants = await fetch_tenants(client, tm)
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during tenant fetch: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during tenant fetch: {e}")
            raise

    last_snapshots = latest_snapshot_per_tenant()
    for tenant in tenants:
        tenant_id = str(tenant.get("id") or "")
        tenant["last_snapshot_at"] = last_snapshots.get(tenant_id)

    return tenants


async def find_tenant(tenant_id: str) -> Optional[Dict[str, Any]]:
    tenants = await fetch_tenants_with_snapshots()
    for t in tenants:
        if str(t.get("id")) == tenant_id:
            return t
    return None


def tenant_name_from_snapshot(data: Dict[str, Any], path: Path) -> str:
    for key in ("tenant_name", "tenantName", "tenant", "tenant_id", "tenantId", "name"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return path.stem


def collect_snapshot_summary() -> Dict[str, Any]:
    """Собрать summary из RAM кэша снапшотов (а не из файлов)."""
    from .snapshots import collect_snapshot_summary_from_cache
    return collect_snapshot_summary_from_cache()


def collect_snapshot_summary_from_files() -> Dict[str, Any]:
    """Резервный вариант: собрать summary из файлов на диске."""
    applications: Set[str] = set()
    hosts: Set[str] = set()
    tenant_hosts: List[Dict[str, Any]] = []

    snapshot_files = sorted(config.SNAPSHOTS_DIR.glob("*.json"))
    for path in snapshot_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(data, dict):
            continue

        tenant_name = tenant_name_from_snapshot(data, path)
        tenant_hosts_set: Set[str] = set()

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
            {"tenant_name": tenant_name, "hosts": sorted(tenant_hosts_set)}
        )

    return {
        "snapshot_files": len(snapshot_files),
        "applications": sorted(applications),
        "hosts": sorted(hosts),
        "tenant_hosts": tenant_hosts,
    }


def settings_payload() -> Dict[str, Any]:
    return {
        "theme": config.UI_THEME,
        "language": config.UI_LANGUAGE,
        "af_url": config.AF_URL,
        "api_login": config.API_LOGIN,
        "api_password": config.API_PASSWORD,
        "verify_ssl": config.VERIFY_SSL,
        "ldap_auth": config.LDAP_AUTH,
        "snapshot_retention_days": config.SNAPSHOT_RETENTION_DAYS,
    }