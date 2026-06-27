#!/usr/bin/env python3
"""Unified entry point for PTAF PRO tools - CLI or Web mode."""
from __future__ import annotations

import argparse
import asyncio
import socket
import sys
import webbrowser
from pathlib import Path

import uvicorn
from loguru import logger

from modules.auth import TokenManager
from modules.config import config
from modules.menu import read_sequence_from_env_or_input, run_sequence
from modules.web_main import app, token_manager


def get_free_port() -> int:
    """Find a free port starting from 8000."""
    port = 8000
    while port < 9000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                port += 1
    return 8000


def run_web_mode() -> None:
    """Start web UI server."""
    port = get_free_port()
    url = f"http://127.0.0.1:{port}/ui"
    
    logger.add(str(config.LOG_FILE), level=config.LOG_LEVEL)
    logger.info(f"Starting PTAF PRO Web UI on {url}")
    
    print(f"\n{'='*50}")
    print(f"PTAF PRO Web UI is running!")
    print(f"Open in browser: {url}")
    print(f"Press Ctrl+C to stop")
    print(f"{'='*50}\n")
    
    try:
        webbrowser.open(url)
    except Exception:
        pass
    
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


async def run_cli_mode(args: argparse.Namespace) -> None:
    """Run CLI menu or specified actions."""
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


def main() -> None:
    from .modules.version import __version__
    
    parser = argparse.ArgumentParser(
        description="PTAF PRO API Tools - CLI and Web UI"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ptaf-tools {__version__}"
    )
    parser.add_argument(
        "--actions",
        help="Comma-separated action codes for CLI mode, e.g. '1,2,3'",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Force CLI mode (show menu)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Force web mode (start web server)",
    )
    args = parser.parse_args()

    # Determine mode: web by default, CLI if --cli or --actions specified
    if args.web or (not args.cli and not args.actions):
        run_web_mode()
    else:
        asyncio.run(run_cli_mode(args))


if __name__ == "__main__":
    main()
