#!/usr/bin/env python3
"""Phase 3c experiment: does a multi-signal ensemble beat single-signal
sub-window stability?

Background: docs/development/candidate-stability-findings.md and the Path
A/B windowing follow-up (run_candidate_windowing_experiment.py) both found
that ema_compare_50_200 + atr_pct_percentile_200's rank_unstable problem is
driven by which market regime lands in which sub-window -- neither more
sub-windows nor a threshold band fixed it. This script tests the platform's
own answer to that failure mode: Aggregator-style majority vote across
independent direction signals, so one signal's bad regime gets outvoted by
others.

Statistical-only, same discipline as the other research scripts -- no
Decision Engine, no provider, no execution.

For every combination of Phase-1 direction candidates (size 2 and 3,
unanimous agreement), this script:
  1. Reports raw (ungated) directional accuracy and active_share -- how often
     the ensemble actually agrees, since requiring agreement trades off
     signal count for (hopefully) quality.
  2. Runs the same sub-window stability check used for single signals
     (evaluate_candidate_stability / summarize_stability) on the *ungated*
     ensemble vote directly used as a BaseSignal, to see whether agreement
     alone (no volatility gate at all) produces sub-window-stable results --
     the single-signal case never did without a gate.
  3. Runs the percentile-threshold sweep (sweep_percentile_thresholds) with
     the ensemble as the base_signal and the platform's atr_pct_percentile_200
     gate on top, to see whether rank_unstable also afflicts the gated
     ensemble or whether combining signals resolves it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.research.direction_phase import DEFAULT_CANDIDATES  # noqa: E402
from src.research.ensemble_phase import (  # noqa: E402
    default_ensemble_grid,
    evaluate_ensemble_agreement,
    make_ensemble_signal,
)
from src.research.magnitude_phase import PERCENTILE_PREDICTORS  # noqa: E402
from src.research.signal_evaluator import compute_forward_targets, load_ohlcv  # noqa: E402
from src.research.stability_phase import (  # noqa: E402
    evaluate_candidate_stability,
    summarize_stability,
    sweep_percentile_thresholds,
)

KNOWN_WIDEST_RANGE_DAYS = 182  # 2026-01-09 -> 2026-07-09, same cache as prior experiments


def _always_open_gate(df: pd.DataFrame) -> pd.Series:
    """A magnitude filter that always passes (>= 0.0) -- the ungated baseline."""
    return pd.Series(100.0, index=df.index)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3c: multi-signal ensemble stability")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--start", default="2026-01-09")
    parser.add_argument("--end", default="2026-07-09")
    parser.add_argument("--source", choices=["exchange", "csv"], default="csv")
    parser.add_argument(
        "--csv-path",
        default=str(_BACKEND / "data" / "cache" / "binance_BTC-USDT_1h_20260109_20260709.csv"),
    )
    parser.add_argument("--filter-name", default="atr_pct_percentile_200")
    parser.add_argument("--horizons", default="14,24,48,72")
    parser.add_argument("--n-windows", type=int, default=3)
    parser.add_argument(
        "--sizes", default="2,3", help="Comma-separated ensemble sizes (unanimous agreement)"
    )
    parser.add_argument(
        "--out",
        default=str(_BACKEND / "data" / "ensemble_stability_experiment_result.json"),
    )
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    span_days = (end - start).days
    if span_days > KNOWN_WIDEST_RANGE_DAYS:
        print(
            f"NOTE: requested range spans {span_days} days, wider than the "
            f"{KNOWN_WIDEST_RANGE_DAYS}-day cache this script was designed against.",
            flush=True,
        )

    horizons = tuple(int(h) for h in args.horizons.split(","))
    sizes = tuple(int(s) for s in args.sizes.split(","))

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
    print(f"Loaded {len(df)} bars ({span_days} calendar days).", flush=True)
    df_with_targets = compute_forward_targets(df, horizons=tuple(sorted({4, 8, 14, 24, *horizons})))

    filter_fn = PERCENTILE_PREDICTORS[args.filter_name]
    grid = default_ensemble_grid(DEFAULT_CANDIDATES, sizes=sizes)
    print(f"\n{len(grid)} ensemble combinations to test (sizes={sizes}).", flush=True)

    payload: dict = {
        "data_range": {"start": args.start, "end": args.end, "bars": len(df)},
        "n_windows": args.n_windows,
        "filter_name": args.filter_name,
        "ensembles": {},
    }

    for label, (member_names, min_agreeing) in grid.items():
        print(f"\n=== {label} ===", flush=True)
        ensemble_fn = make_ensemble_signal(
            member_names, min_agreeing=min_agreeing, candidates=DEFAULT_CANDIDATES
        )

        agreement = evaluate_ensemble_agreement(
            df_with_targets,
            ensemble_fn,
            member_names=member_names,
            min_agreeing=min_agreeing,
            horizons=horizons,
        )
        acc_str = ", ".join(f"h{h}={acc:.1f}%" for h, acc in agreement.accuracy_by_horizon.items())
        print(
            f"  active_share={agreement.active_share:.1f}% "
            f"({agreement.active_bars}/{agreement.total_bars} bars)  accuracy: {acc_str}",
            flush=True,
        )

        entry: dict = {
            "member_names": list(member_names),
            "min_agreeing": min_agreeing,
            "active_share": agreement.active_share,
            "active_bars": agreement.active_bars,
            "accuracy_by_horizon": agreement.accuracy_by_horizon,
            "ungated_stability": {},
            "gated_sweep": {},
        }

        # (2) Ungated sub-window stability: does agreement alone (no
        # volatility gate) survive sub-windowing where single signals didn't?
        for horizon in horizons:
            sub_results = evaluate_candidate_stability(
                df_with_targets,
                base_signal=ensemble_fn,
                magnitude_filter=_always_open_gate,
                percentile_threshold=0.0,  # gate always open -- ungated baseline
                horizon=horizon,
                n_windows=args.n_windows,
            )
            verdict = summarize_stability(sub_results)
            net_str = ", ".join(
                f"w{r.window_index}: n={r.filtered_stats.trades} "
                f"net_exp={r.filtered_stats_net_fees.expectancy:+.3f}% "
                f"wr_delta={r.win_rate_improvement_pp:+.1f}pp"
                for r in sub_results
            )
            print(
                f"  [ungated h={horizon}] passes_repeatability={verdict.passes_repeatability} "
                f"({verdict.detail})",
                flush=True,
            )
            print(f"    {net_str}", flush=True)
            entry["ungated_stability"][str(horizon)] = {
                "passes_repeatability": verdict.passes_repeatability,
                "detail": verdict.detail,
                "windows": [
                    {
                        "window_index": r.window_index,
                        "trades": r.filtered_stats.trades,
                        "net_expectancy": r.filtered_stats_net_fees.expectancy,
                        "win_rate_improvement_pp": r.win_rate_improvement_pp,
                        "regime_concentration_flag": r.regime_concentration_flag,
                    }
                    for r in sub_results
                ],
            }

        # (3) Gated sweep: with the platform's own volatility gate on top of
        # the ensemble vote, does rank_unstable still fire?
        for horizon in horizons:
            sweep = sweep_percentile_thresholds(
                df_with_targets,
                base_signal=ensemble_fn,
                magnitude_filter=filter_fn,
                horizon=horizon,
                percentile_thresholds=(75.0, 80.0, 85.0, 90.0, 95.0),
                n_windows=args.n_windows,
            )
            print(
                f"  [gated h={horizon}] best_threshold={sweep.best_threshold_on_train} "
                f"rank_unstable={sweep.best_threshold_rank_unstable} "
                f"holdout={sweep.holdout_verdict_for_best}",
                flush=True,
            )
            entry["gated_sweep"][str(horizon)] = {
                "best_threshold_on_train": sweep.best_threshold_on_train,
                "rank_unstable": sweep.best_threshold_rank_unstable,
                "holdout_verdict": sweep.holdout_verdict_for_best,
            }

        payload["ensembles"][label] = entry

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
