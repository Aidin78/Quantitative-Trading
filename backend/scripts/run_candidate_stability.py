#!/usr/bin/env python3
"""Run Phase 3b: stability/repeatability check for a single Phase-3 candidate.

Statistical-only, same as run_signal_research.py — no Decision Engine, no
execution. Slices the candidate's date range into sub-windows, checks whether
its win-rate improvement and trading metrics (expectancy, profit factor,
avg win/loss, max drawdown, fee/slippage-adjusted performance) repeat across
them and across regimes, sweeps the magnitude-gate percentile threshold
(p75-p95 by default) with a held-out final sub-window, and compares the
candidate against ATR-based volatility filter/sizing overlays.

Run run_signal_research.py --phase 3 first to find a candidate's
base_signal/filter_name/horizon before running this script.
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

from src.research.direction_phase import DEFAULT_CANDIDATES  # noqa: E402
from src.research.magnitude_phase import PERCENTILE_PREDICTORS  # noqa: E402
from src.research.report import (  # noqa: E402
    build_stability_payload,
    print_stability_summary,
)
from src.research.signal_evaluator import (  # noqa: E402
    DEFAULT_HORIZONS,
    compute_forward_targets,
    load_ohlcv,
)
from src.research.stability_phase import (  # noqa: E402
    evaluate_candidate_stability,
    evaluate_volatility_overlay,
    summarize_stability,
    sweep_percentile_thresholds,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3b: candidate stability check")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-07-18")
    parser.add_argument(
        "--source", choices=["exchange", "csv"], default="exchange", help="OHLCV source"
    )
    parser.add_argument("--csv-path", default=None)
    parser.add_argument(
        "--base-signal",
        default="market_structure_bias_5",
        choices=list(DEFAULT_CANDIDATES.keys()),
        help="Which Phase-1 base signal the candidate gates",
    )
    parser.add_argument(
        "--filter-name",
        default="atr_pct_percentile_200",
        choices=list(PERCENTILE_PREDICTORS.keys()),
        help="Which Phase-2 magnitude filter the candidate gates on",
    )
    parser.add_argument("--percentile-threshold", type=float, default=70.0)
    parser.add_argument("--horizon", type=int, default=14)
    parser.add_argument("--sub-windows", type=int, default=3)
    parser.add_argument(
        "--percentiles",
        default="75,80,85,90,95",
        help="Comma-separated percentile thresholds to sweep as a hyperparameter",
    )
    parser.add_argument(
        "--out",
        default=str(_BACKEND / "data" / "candidate_stability_result.json"),
    )
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    percentile_thresholds = tuple(float(p) for p in args.percentiles.split(","))

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
    horizons = tuple(sorted({*DEFAULT_HORIZONS, args.horizon}))
    df_with_targets = compute_forward_targets(df, horizons=horizons)

    base_signal_fn = DEFAULT_CANDIDATES[args.base_signal]
    filter_fn = PERCENTILE_PREDICTORS[args.filter_name]

    sub_window_results = evaluate_candidate_stability(
        df_with_targets,
        base_signal=base_signal_fn,
        magnitude_filter=filter_fn,
        percentile_threshold=args.percentile_threshold,
        horizon=args.horizon,
        n_windows=args.sub_windows,
    )
    stability_verdict = summarize_stability(sub_window_results)

    percentile_sweep = None
    if args.sub_windows >= 2:
        percentile_sweep = sweep_percentile_thresholds(
            df_with_targets,
            base_signal=base_signal_fn,
            magnitude_filter=filter_fn,
            horizon=args.horizon,
            percentile_thresholds=percentile_thresholds,
            n_windows=args.sub_windows,
        )

    volatility_overlay = evaluate_volatility_overlay(
        df_with_targets,
        base_signal=base_signal_fn,
        magnitude_filter=filter_fn,
        percentile_threshold=args.percentile_threshold,
        horizon=args.horizon,
    )

    payload = build_stability_payload(
        base_signal=args.base_signal,
        filter_name=args.filter_name,
        horizon=args.horizon,
        sub_window_results=sub_window_results,
        stability_verdict=stability_verdict,
        percentile_sweep=percentile_sweep,
        volatility_overlay=volatility_overlay,
    )
    print_stability_summary(payload)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
