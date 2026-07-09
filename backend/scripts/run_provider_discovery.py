#!/usr/bin/env python3
"""Run a provider-discovery optimization sweep (Optuna, on/off flags)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.validation.optimizer import (  # noqa: E402
    OptimizationSpace,
    enabled_provider_labels,
    run_optimization,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provider discovery optimization sweep")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-01-05")
    parser.add_argument("--max-trials", type=int, default=80)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--holdout-ratio", type=float, default=0.2)
    parser.add_argument("--min-trades", type=int, default=30)
    parser.add_argument("--csv-path", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Only sample trial params (no backtests); low memory",
    )
    return parser.parse_args()


def _resolve_csv(path: str | None) -> str | None:
    if path:
        return path
    for name in ("sample_btc_1h.csv", "ohlcv_btc_1h.csv"):
        candidate = _BACKEND / "tests" / "fixtures" / name
        if candidate.exists():
            return str(candidate)
    return None


def _print_best(result) -> None:
    best = result.best
    if best is None:
        print("No eligible best trial (check min_trades / return guardrails).")
        if result.fallback_trial:
            best = result.fallback_trial
            print("Using fallback trial instead.")
        else:
            return
    labels = enabled_provider_labels(best.params)
    agree = best.params.get("min_agreeing_providers", "?")
    print("\n=== Best provider combo ===")
    print(f"Providers: {', '.join(labels) if labels else '(none)'}")
    print(f"min_agreeing_providers: {agree}")
    print(f"composite_score: {best.composite_score}")
    print(f"test_score: {best.test_score}")
    print(f"test_return_pct: {best.test_outcome.get('return_pct') if best.test_outcome else None}")
    print(f"test_trades: {best.test_outcome.get('total_trades') if best.test_outcome else None}")
    print(f"trial_id: {best.trial_id}")


async def _run() -> int:
    args = _parse_args()
    space = OptimizationSpace.provider_discovery()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)

    if args.sample_only:
        from src.validation.optimizer import generate_trials_optuna

        trials = generate_trials_optuna(space, max_trials=args.max_trials, seed=args.seed)
        print(f"Sampled {len(trials)} discovery trials (no backtest).")
        for index, params in enumerate(trials[:5], start=1):
            labels = enabled_provider_labels(params)
            labels_text = ", ".join(labels) if labels else "(none)"
            print(f"  {index}. {labels_text} " f"(agree>={params.get('min_agreeing_providers')})")
        if len(trials) > 5:
            print(f"  ... and {len(trials) - 5} more")
        return 0

    csv_path = _resolve_csv(args.csv_path)
    result = await run_optimization(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=start,
        end=end,
        source="csv",
        csv_path=csv_path,
        train_ratio=args.train_ratio,
        max_trials=args.max_trials,
        top_k=args.top_k,
        space=space,
        min_trades=args.min_trades,
        holdout_ratio=args.holdout_ratio,
        local_refine=False,
        search_method="optuna",
        seed=args.seed,
    )
    print(f"Completed {len(result.trials)} trials.")
    _print_best(result)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
