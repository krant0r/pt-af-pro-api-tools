from __future__ import annotations

import os
from typing import Awaitable, Callable, Dict, List

from loguru import logger

from .auth import TokenManager
from .snapshots import export_all_tenant_snapshots
from .rules_actions import (
    export_actions_for_all_tenants,
    export_rules_for_all_tenants,
)


ActionFunc = Callable[[TokenManager], Awaitable[None]]


async def _action_export_snapshots(tm: TokenManager) -> None:
    await export_all_tenant_snapshots(tm)


async def _action_export_rules(tm: TokenManager) -> None:
    await export_rules_for_all_tenants(tm)


async def _action_export_actions(tm: TokenManager) -> None:
    files, errors = await export_actions_for_all_tenants(tm)
    if errors:
        for err in errors:
            logger.error(err)
    logger.info(f"Exported {len(files)} action files")


ACTIONS: Dict[int, ActionFunc] = {
    1: _action_export_snapshots,
    2: _action_export_rules,
    3: _action_export_actions,
}

ACTION_TITLES: Dict[int, str] = {
    1: "Export full config snapshots for all tenants",
    2: "Export rules for all tenants",
    3: "Export actions for all tenants",
}


def parse_sequence(seq: str) -> List[int]:
    """
    Разбирает строку вида "1,2,3" -> [1,2,3]
    Пробелы игнорируются.
    """
    items: List[int] = []
    for part in seq.replace(" ", "").split(","):
        if not part:
            continue
        try:
            items.append(int(part))
        except ValueError:
            raise ValueError(f"Invalid action code in sequence: {part!r}")
    return items


def interactive_print_menu() -> None:
    print("=== PTAF PRO API tools menu ===")
    for code in sorted(ACTIONS):
        print(f"{code}. {ACTION_TITLES[code]}")
    print("0. Exit")


def read_sequence_from_env_or_input() -> str:
    seq = os.getenv("PTAF_ACTION_SEQUENCE", "").strip()
    if seq:
        logger.info(f"Using PTAF_ACTION_SEQUENCE={seq}")
        return seq

    interactive_print_menu()
    seq = input(
        "Enter comma-separated sequence of actions "
        "(e.g. 1,2,3; 0 to exit): "
    ).strip()
    return seq


async def run_sequence(tm: TokenManager, seq_str: str) -> None:
    """
    Выполняет последовательность действий по их числовым кодам.
    """
    codes = parse_sequence(seq_str)
    for code in codes:
        if code == 0:
            logger.info("Exit code encountered, stopping sequence")
            break
        func = ACTIONS.get(code)
        if not func:
            logger.error(f"Unknown action code: {code}")
            continue
        logger.info(f"Running action {code}: {ACTION_TITLES[code]}")
        await func(tm)
