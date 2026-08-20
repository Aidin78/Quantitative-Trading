#!/usr/bin/env python3
"""Provider edge scorecard CLI: solo/family diagnostics on Pass2-style windows."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.validation.provider_edge_scorecard import (  # noqa: E402
    print_scorecard_summary,
    run_scorecard,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provider edge scorecard / diagnostic")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2026-07-18")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument(
        "--mode",
        choices=["full", "pass2"],
        default="full",
        help="full = 8 solos + family combos + EMA/BB; pass2 = A-D EMA/BB only",
    )
    parser.add_argument("--no-fee-sensitivity", action="store_true")
    parser.add_argument(
        "--out",
        default=str(_BACKEND / "data" / "provider_edge_scorecard.json"),
    )
    return parser.parse_args()


async def _amain() -> int:
    args = _parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    payload = await run_scorecard(
        start=start,
        end=end,
        mode=args.mode,
        symbol=args.symbol,
        timeframe=args.timeframe,
        fee_sensitivity=not args.no_fee_sensitivity,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)
    print_scorecard_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain()))
