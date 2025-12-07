from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

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
    name = _slugify(str(tenant.get("name") or tenant.get("displayName") or tenant["id"]))
    tenant_id = tenant.get("id", "unknown")
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fname = f"{ts}_{name}_{tenant_id}.snapshot.json"
    return config.SNAPSHOTS_DIR / fname


async def export_all_tenant_snapshots(tm: TokenManager) -> List[Path]:
    """
    Stage 1:
      1. Authorize in API.
      2. Iterate over all tenants and export full config snapshot for each.
      3. Save snapshots into files under config.SNAPSHOTS_DIR.

    Returns list of created file paths.
    """
    created_files: List[Path] = []

    async with httpx.AsyncClient(
        verify=config.VERIFY_SSL,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        # 1. Ensure we can auth at all
        token = await tm.ensure_base_token(client)
        if not token:
            raise RuntimeError("Unable to obtain base access token (check credentials)")

        # 2. Fetch tenants
        tenants = await fetch_tenants(client, tm)
        if not tenants:
            logger.warning("No tenants returned by API")
            return []

        # 3. For each tenant – switch token & GET snapshot
        for t in tenants:
            t_id = t.get("id")
            t_name = t.get("name") or t.get("displayName") or t_id
            logger.info(f"Exporting snapshot for tenant {t_name} ({t_id})")

            auth = TenantAuth(tm, tenant_id=t_id)
            url = f"{config.AF_URL}{config.SNAPSHOT_ENDPOINT}"

            resp = await client.get(url, auth=auth)
            if resp.status_code != 200:
                logger.error(
                    f"Snapshot export failed for tenant {t_name} ({t_id}): "
                    f"{resp.status_code} {resp.text}"
                )
                continue

            try:
                data = resp.json()
            except Exception as e:
                logger.exception(f"Invalid JSON in snapshot for tenant {t_name}: {e!r}")
                continue

            path = _snapshot_filename(t)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                created_files.append(path)
                logger.success(f"Snapshot saved: {path}")
            except Exception as e:
                logger.exception(f"Failed to save snapshot to {path}: {e!r}")

    if not created_files:
        logger.warning("No snapshots were successfully exported")
    else:
        logger.info(f"Exported {len(created_files)} snapshots to {config.SNAPSHOTS_DIR}")

    return created_files
