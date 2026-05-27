from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

import httpx
from loguru import logger

from .auth import TokenManager, TenantAuth
from .config import config
from .tenants import fetch_tenants


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "tenant"


def _snapshot_filename(tenant: Dict[str, Any]) -> Path:
    name = _slugify(
        str(tenant.get("name") or tenant.get("displayName") or tenant.get("id"))
    )
    tenant_id = tenant.get("id", "unknown")
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fname = f"{ts}_{name}_{tenant_id}.snapshot.json"
    return config.SNAPSHOTS_DIR / fname


def cleanup_old_snapshots() -> int:
    """
    Удаляет снапшоты старше SNAPSHOT_RETENTION_DAYS, если параметр задан.

    Возвращает количество удалённых файлов.
    """

    retention_days = config.SNAPSHOT_RETENTION_DAYS
    if not retention_days:
        return 0

    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    removed = 0

    for path in config.SNAPSHOTS_DIR.glob("*.snapshot.json"):
        try:
            mtime = datetime.utcfromtimestamp(path.stat().st_mtime)
        except OSError:
            continue

        if mtime < cutoff:
            try:
                path.unlink()
                removed += 1
            except OSError:
                logger.warning(f"Failed to delete old snapshot: {path}")

    if removed:
        logger.info(
            f"Removed {removed} snapshots older than {retention_days} days"
        )

    return removed


def _tenant_id_from_snapshot_path(path: Path) -> Optional[str]:
    # Убираем расширение .snapshot.json полностью
    name = path.name
    if not name.endswith('.snapshot.json'):
        return None
    base = name[:-len('.snapshot.json')]  # отрезаем .snapshot.json
    parts = base.rsplit("_", 1)
    if len(parts) < 2:
        return None
    return parts[-1]


def _timestamp_from_snapshot_path(path: Path) -> Optional[datetime]:
    name = path.name
    if not name.endswith('.snapshot.json'):
        return None
    base = name[:-len('.snapshot.json')]
    prefix = base.split("_", 1)[0]
    try:
        return datetime.strptime(prefix, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return None


def latest_snapshot_per_tenant() -> Dict[str, str]:
    """
    Returns mapping tenant_id -> latest snapshot timestamp (ISO string, UTC).

    If timestamp cannot be parsed from filename, falls back to file mtime.
    """

    latest: Dict[str, datetime] = {}

    for path in config.SNAPSHOTS_DIR.glob("*.snapshot.json"):
        tenant_id = _tenant_id_from_snapshot_path(path)
        
        if not tenant_id:
            continue

        ts = _timestamp_from_snapshot_path(path)
        if not ts:
            try:
                ts = datetime.utcfromtimestamp(path.stat().st_mtime)
            except OSError:
                continue

        current = latest.get(tenant_id)
        if not current or ts > current:
            latest[tenant_id] = ts

    return {
        tid: dt.replace(microsecond=0).isoformat() + "Z" for tid, dt in latest.items()
    }


async def export_snapshot_for_tenant(
    client: httpx.AsyncClient,
    tm: TokenManager,
    tenant: Dict[str, Any],
) -> Optional[Path]:
    tenant_id = str(tenant.get("id"))
    if not tenant_id:
        logger.error(f"Tenant object has no 'id': {tenant}")
        return None

    fname = _snapshot_filename(tenant)
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
    fname.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.success(f"[tenant={tenant_id}] Snapshot written to {fname}")
    return fname


async def export_all_tenant_snapshots(tm: TokenManager) -> List[Path]:
    created_files: List[Path] = []

    removed = cleanup_old_snapshots()
    if removed:
        logger.info(f"Cleanup complete: {removed} old snapshots removed")

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
