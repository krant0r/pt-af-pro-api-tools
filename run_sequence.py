#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from modules.auth import TokenManager
from modules.config import config
from modules.menu import read_sequence_from_env_or_input, run_sequence


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Run PTAF PRO actions sequence (1,2,3,...) and exit."
    )
    parser.add_argument(
        "--actions",
        help="Comma-separated action codes, e.g. '1,2,3'. "
        "If omitted, uses PTAF_ACTION_SEQUENCE env or interactive prompt.",
    )
    args = parser.parse_args()

    logger.add(str(config.LOG_FILE), level=config.LOG_LEVEL)

    if args.actions:
        seq = args.actions.strip()
    else:
        seq = read_sequence_from_env_or_input()
    if not seq:
        logger.info("No sequence specified, exiting")
        return

    tm = TokenManager()
    await run_sequence(tm, seq)


if __name__ == "__main__":
    asyncio.run(_main())
