#!/usr/bin/env python3
"""Path A / Path B follow-up on ``docs/development/candidate-stability-findings.md``.

Statistical-only, same discipline as ``run_candidate_stability.py`` — no
Decision Engine, no provider, no execution. Tests the two remedies that
document's "next steps" proposed for the ``ema_compare_50_200 +
atr_pct_percentile_200`` candidate's ``rank_unstable`` percentile-threshold
sweep:

Path A: does using 4-5 sub-windows instead of 3 make the *winning* percentile
threshold more consistent across training sub-windows (still a single-point
selection, just sliced finer)?

Path B: does committing upfront to a threshold *band* (p85-p95) — never
selecting a single "best" point — produce net-of-fees-positive results across
every sub-window at every threshold in the band, i.e. a generalizable edge
rather than a per-window optimum?

Both paths reuse the same 6-month BTC/USDT 1h cached CSV the original finding
document used (2026-01-09 to 2026-07-09) — this is the widest contiguous
range available in ``data/cache/`` in this environment (network access to
pull a longer history was unavailable when this script was written); Path A
is therefore a finer re-slicing of the same range, not a longer one. See the
printed WARNING if this script is ever run somewhere more history is
available and start/end are widened.
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
from src.research.signal_evaluator import compute_forward_targets, load_ohlcv  # noqa: E402
from src.research.stability_phase import (  # noqa: E402
    evaluate_threshold_band,
    sweep_percentile_thresholds,
)

KNOWN_WIDEST_RANGE_DAYS = 182  # 2026-01-09 -> 2026-07-09, the cached CSV this script targets


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Path A (more sub-windows) / Path B (threshold band) experiment"
    )
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--start", default="2026-01-09")
    parser.add_argument("--end", default="2026-07-09")
    parser.add_argument("--source", choices=["exchange", "csv"], default="csv")
    parser.add_argument(
        "--csv-path",
        default=str(_BACKEND / "data" / "cache" / "binance_BTC-USDT_1h_20260109_20260709.csv"),
    )
    parser.add_argument("--base-signal", default="ema_compare_50_200 (slow)")
    parser.add_argument("--filter-name", default="atr_pct_percentile_200")
    parser.add_argument(
        "--horizons",
        default="48,72",
        help="Comma-separated horizons to test (must be <= the widest DEFAULT_HORIZONS union)",
    )
    parser.add_argument(
        "--path-a-windows",
        default="3,4,5",
        help="Comma-separated sub-window counts to compare for Path A",
    )
    parser.add_argument(
        "--band",
        default="85,90,95",
        help="Comma-separated percentile thresholds forming the Path B band",
    )
    parser.add_argument(
        "--out",
        default=str(_BACKEND / "data" / "candidate_windowing_experiment_result.json"),
    )
    return parser.parse_args()


def _fmt_pp(value: float) -> str:
    return f"{value:+.1f}pp" if value == value else "nan"  # noqa: PLR0124 (NaN check)


async def _run() -> int:
    args = _parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    span_days = (end - start).days
    if span_days > KNOWN_WIDEST_RANGE_DAYS:
        print(
            f"NOTE: requested range spans {span_days} days, wider than the "
            f"{KNOWN_WIDEST_RANGE_DAYS}-day cache this script was designed against — "
            "if this succeeds, Path A can now test a genuinely longer history, not just "
            "a finer re-slice of the same one.",
            flush=True,
        )

    horizons = tuple(int(h) for h in args.horizons.split(","))
    path_a_windows = tuple(int(w) for w in args.path_a_windows.split(","))
    band = tuple(float(p) for p in args.band.split(","))

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

    base_signal_fn = DEFAULT_CANDIDATES[args.base_signal]
    filter_fn = PERCENTILE_PREDICTORS[args.filter_name]

    payload: dict = {
        "base_signal": args.base_signal,
        "filter_name": args.filter_name,
        "data_range": {"start": args.start, "end": args.end, "bars": len(df)},
        "path_a": {},
        "path_b": {},
    }

    print("\n=== PATH A: more sub-windows, single-point selection ===", flush=True)
    for horizon in horizons:
        payload["path_a"][str(horizon)] = {}
        print(f"\n-- horizon h={horizon} --", flush=True)
        for n_windows in path_a_windows:
            sweep = sweep_percentile_thresholds(
                df_with_targets,
                base_signal=base_signal_fn,
                magnitude_filter=filter_fn,
                horizon=horizon,
                percentile_thresholds=(75.0, 80.0, 85.0, 90.0, 95.0),
                n_windows=n_windows,
            )
            per_window_net = []
            for point in sweep.points:
                if point.percentile_threshold != sweep.best_threshold_on_train:
                    continue
                for r in point.train_stats:
                    per_window_net.append((r.window_index, r.filtered_stats_net_fees.expectancy))
                if point.holdout_stats is not None:
                    per_window_net.append(
                        (
                            point.holdout_stats.window_index,
                            point.holdout_stats.filtered_stats_net_fees.expectancy,
                        )
                    )
            per_window_net.sort()
            net_str = ", ".join(f"{e:+.3f}%" for _, e in per_window_net)
            print(
                f"  n_windows={n_windows}: best_threshold_on_train="
                f"{sweep.best_threshold_on_train} "
                f"rank_unstable={sweep.best_threshold_rank_unstable} "
                f"holdout={sweep.holdout_verdict_for_best}",
                flush=True,
            )
            print(f"    net_expectancy per window (train..holdout): {net_str}", flush=True)
            payload["path_a"][str(horizon)][str(n_windows)] = {
                "best_threshold_on_train": sweep.best_threshold_on_train,
                "rank_unstable": sweep.best_threshold_rank_unstable,
                "holdout_verdict": sweep.holdout_verdict_for_best,
                "per_window_net_expectancy": per_window_net,
                "points": [
                    {
                        "threshold": p.percentile_threshold,
                        "train_avg_improvement_pp": (
                            sum(
                                r.win_rate_improvement_pp
                                for r in p.train_stats
                                if r.win_rate_improvement_pp == r.win_rate_improvement_pp
                            )
                            / max(
                                1,
                                sum(
                                    1
                                    for r in p.train_stats
                                    if r.win_rate_improvement_pp == r.win_rate_improvement_pp
                                ),
                            )
                        ),
                        "holdout_improvement_pp": (
                            p.holdout_stats.win_rate_improvement_pp
                            if p.holdout_stats is not None
                            else None
                        ),
                    }
                    for p in sweep.points
                ],
            }

    print("\n=== PATH B: threshold band, no single-point selection ===", flush=True)
    for horizon in horizons:
        print(f"\n-- horizon h={horizon}, band=p{band[0]:.0f}-p{band[-1]:.0f} --", flush=True)
        payload["path_b"][str(horizon)] = {}
        for n_windows in path_a_windows:
            band_result = evaluate_threshold_band(
                df_with_targets,
                base_signal=base_signal_fn,
                magnitude_filter=filter_fn,
                horizon=horizon,
                percentile_thresholds=band,
                n_windows=n_windows,
            )
            print(
                f"  n_windows={n_windows}: {band_result.detail} "
                f"-> band_is_consistent={band_result.band_is_consistent}",
                flush=True,
            )
            for w in range(n_windows):
                window_rows = [r for r in band_result.rows if r.window_index == w]
                row_str = ", ".join(
                    f"p{r.percentile_threshold:.0f}: n={r.trades} "
                    f"net_exp={r.net_expectancy:+.3f}%"
                    + (" [<min_trades]" if r.below_min_trades else "")
                    for r in sorted(window_rows, key=lambda r: r.percentile_threshold)
                )
                print(f"    window {w + 1}/{n_windows}: {row_str}", flush=True)
            payload["path_b"][str(horizon)][str(n_windows)] = {
                "band_is_consistent": band_result.band_is_consistent,
                "windows_evaluated": band_result.windows_evaluated,
                "windows_all_positive_across_band": band_result.windows_all_positive_across_band,
                "detail": band_result.detail,
                "rows": [
                    {
                        "threshold": r.percentile_threshold,
                        "window_index": r.window_index,
                        "trades": r.trades,
                        "net_expectancy": r.net_expectancy,
                        "win_rate_improvement_pp": r.win_rate_improvement_pp,
                        "below_min_trades": r.below_min_trades,
                    }
                    for r in band_result.rows
                ],
            }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
