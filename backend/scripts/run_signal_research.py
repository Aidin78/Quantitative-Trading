#!/usr/bin/env python3
"""Run the signal-research pipeline (Phase 1-3: direction, magnitude, classification).

Statistical-only research over raw OHLCV — no Decision Engine, no execution.
Meant to run before ever building/testing a new signal provider, so a
candidate signal is screened for real predictive power before paying for a
full validation backtest (Phase 4, run separately via
``run_provider_discovery.py`` / ``provider_edge_diagnostic.py``).
"""

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

from src.research.classification_phase import (  # noqa: E402
    run_classification_phase,
)
from src.research.direction_phase import DEFAULT_CANDIDATES, run_direction_phase  # noqa: E402
from src.research.magnitude_phase import (  # noqa: E402
    PERCENTILE_PREDICTORS,
    run_magnitude_phase,
)
from src.research.report import (  # noqa: E402
    build_classification_payload,
    build_direction_payload,
    build_magnitude_payload,
    print_classification_summary,
    print_direction_summary,
    print_magnitude_summary,
)
from src.research.signal_evaluator import compute_forward_targets, load_ohlcv  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Signal-research pipeline (Phase 1-3)")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-07-18")
    parser.add_argument(
        "--source",
        choices=["exchange", "csv"],
        default="exchange",
        help="OHLCV source (exchange preferred; csv falls back to fixtures)",
    )
    parser.add_argument("--csv-path", default=None)
    parser.add_argument(
        "--phase",
        choices=["1", "2", "3", "all"],
        default="all",
        help="Which phase to run (default: all, run sequentially)",
    )
    parser.add_argument(
        "--out",
        default=str(_BACKEND / "data" / "signal_research_result.json"),
        help="Where to write the machine-readable JSON result",
    )
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)

    print(
        f"Loading OHLCV: {args.symbol} {args.timeframe} {args.start}->{args.end} "
        f"source={args.source}",
        flush=True,
    )
    df = await load_ohlcv(
        source=args.source,
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=start,
        end=end,
        csv_path=args.csv_path,
    )
    print(f"Loaded {len(df)} bars.", flush=True)
    df_with_targets = compute_forward_targets(df)

    payload: dict = {
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "start": args.start,
        "end": args.end,
        "bars": len(df),
    }

    phases = ["1", "2", "3"] if args.phase == "all" else [args.phase]

    direction_results = None
    if "1" in phases:
        direction_results = run_direction_phase(df_with_targets)
        direction_payload = build_direction_payload(direction_results)
        print_direction_summary(direction_payload)
        payload["phase_1"] = direction_payload

    if "2" in phases:
        magnitude_results = run_magnitude_phase(df_with_targets)
        magnitude_payload = build_magnitude_payload(magnitude_results)
        print_magnitude_summary(magnitude_payload)
        payload["phase_2"] = magnitude_payload

    if "3" in phases:
        classification_results = run_classification_phase(
            df_with_targets,
            base_signals=DEFAULT_CANDIDATES,
            magnitude_filters=PERCENTILE_PREDICTORS,
        )
        classification_payload = build_classification_payload(classification_results)
        print_classification_summary(classification_payload)
        payload["phase_3"] = classification_payload

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
