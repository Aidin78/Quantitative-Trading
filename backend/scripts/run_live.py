#!/usr/bin/env python3
"""CLI entry point for live/paper trading scheduler."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.core.settings import load_app_yaml_config
from src.db.session import get_async_engine, init_db
from src.runtime.live_manager import live_manager


def _parse_args() -> argparse.Namespace:
    app = load_app_yaml_config()
    parser = argparse.ArgumentParser(description="Run live/paper trading scheduler")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--symbol", default=app.default_symbols[0])
    parser.add_argument("--timeframe", default=app.timeframes[0])
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    parser.add_argument("--no-db", action="store_true", help="Skip database init")
    parser.add_argument("--revision-id", default=None)
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    if not args.no_db:
        await init_db(get_async_engine())

    if args.once:
        from src.runtime.live_stack import run_live_cycle

        await run_live_cycle(
            args.symbol,
            args.timeframe,
            mode=args.mode,
            persist_db=not args.no_db,
        )
        print(f"Completed single {args.mode} cycle for {args.symbol} {args.timeframe}")
        return 0

    await live_manager.start(
        mode=args.mode,
        jobs=[(args.symbol, args.timeframe)],
        revision_id=args.revision_id,
    )
    print(f"Live scheduler started ({args.mode}) for {args.symbol} {args.timeframe}")

    stop_event = asyncio.Event()

    def _handle_sig(*_args) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)
    await stop_event.wait()
    await live_manager.stop()
    print("Live scheduler stopped")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
