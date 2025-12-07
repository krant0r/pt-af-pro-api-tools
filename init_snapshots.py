from __future__ import annotations

import asyncio

from loguru import logger

from modules.auth import TokenManager
from modules.config import config
from modules.snapshots import export_all_tenant_snapshots


async def _main() -> None:
    logger.add(str(config.LOG_FILE), level=config.LOG_LEVEL)
    tm = TokenManager()
    paths = await export_all_tenant_snapshots(tm)
    if paths:
        logger.info(f"Exported {len(paths)} tenant snapshots")
    else:
        logger.warning("No snapshots were exported")


if __name__ == "__main__":
    asyncio.run(_main())
