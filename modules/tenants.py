from __future__ import annotations

from typing import Any, Dict, List

import httpx
from loguru import logger

from .auth import TokenManager, TenantAuth
from .config import config


async def fetch_tenants(
    client: httpx.AsyncClient,
    tm: TokenManager,
) -> List[Dict[str, Any]]:
    """
    Returns list of tenants visible to current account.

    PTAF PRO returns either:
      {
        "items": [
          {"id": "...", "name": "...", ...},
          ...
        ]
      }
    or a plain list.
    """
    url = f"{config.AF_URL}{config.TENANTS_ENDPOINT}"
    logger.debug(f"Fetching tenants from {url}")
    auth = TenantAuth(tm, tenant_id=None)
    r = await client.get(url, auth=auth)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "items" in data:
        tenants = data["items"]
    elif isinstance(data, list):
        tenants = data
    else:
        raise RuntimeError(f"Unsupported tenants response format: {type(data)}")

    logger.info(f"Fetched {len(tenants)} tenants")
    return tenants
