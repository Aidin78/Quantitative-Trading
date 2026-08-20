#!/usr/bin/env python3
"""Optuna sweep: Bollinger-solo threshold/exit tuning on Pass2-style windows."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.api.services.optimization_service import result_to_dict  # noqa: E402
from src.validation.optimizer import OptimizationSpace, run_optimization  # noqa: E402
from src.validation.provider_edge_scorecard import evaluate_params_scorecard  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bollinger solo threshold tuning")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2026-07-18")
    parser.add_argument("--max-trials", type=int, default=60)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--holdout-ratio", type=float, default=0.2)
    parser.add_argument("--min-trades", type=int, default=15)
    parser.add_argument("--csv-path", default=None)
    parser.add_argument(
        "--source",
        choices=["exchange", "csv"],
        default="exchange",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-parallel-trials", type=int, default=4)
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Only sample trial params (no backtests)",
    )
    parser.add_argument(
        "--skip-rescore",
        action="store_true",
        help="Skip post-sweep scorecard verdict on best params",
    )
    parser.add_argument(
        "--out",
        default=str(_BACKEND / "data" / "bb_solo_tuning_result.json"),
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


def _print_best(result: Any) -> None:
    best = result.best
    if best is None:
        print("No eligible best trial (check min_trades / return guardrails).")
        if result.fallback_trial:
            best = result.fallback_trial
            print("Using fallback trial instead.")
        else:
            return
    p = best.params
    print("\n=== Best BB solo params ===")
    print(f"trial_id: {best.trial_id}")
    print(f"composite_score: {best.composite_score}")
    print(
        f"bb_period={p.get('bb_period')} bb_std={p.get('bb_std')} "
        f"bb_max_adx={p.get('bb_max_adx')} bb_avoid_high_vol={p.get('bb_avoid_high_vol')}"
    )
    print(
        f"min_confidence={p.get('min_confidence')} "
        f"sl={p.get('sl_atr_mult')} tp={p.get('tp_atr_mult')} "
        f"max_bars={p.get('max_bars_in_trade')} min_atr_pct={p.get('min_atr_pct')}"
    )
    train = best.train_outcome or {}
    test = best.test_outcome or {}
    print(
        f"train: ret={train.get('return_pct')} trades={train.get('total_trades')} "
        f"score={best.train_score}"
    )
    print(
        f"test: ret={test.get('return_pct')} trades={test.get('total_trades')} "
        f"score={best.test_score}"
    )


async def _run() -> int:
    args = _parse_args()
    space = OptimizationSpace.bb_solo_tuning()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)

    if args.sample_only:
        from src.validation.optimizer import generate_trials_optuna

        trials = generate_trials_optuna(space, max_trials=args.max_trials, seed=args.seed)
        print(f"Sampled {len(trials)} BB solo trials (no backtest).")
        for index, params in enumerate(trials[:5], start=1):
            print(
                f"  {index}. period={params.get('bb_period')} std={params.get('bb_std')} "
                f"max_adx={params.get('bb_max_adx')} conf={params.get('min_confidence')} "
                f"sl={params.get('sl_atr_mult')} tp={params.get('tp_atr_mult')}"
            )
        if len(trials) > 5:
            print(f"  ... and {len(trials) - 5} more")
        return 0

    csv_path = _resolve_csv(args.csv_path) if args.source == "csv" else args.csv_path
    if args.source == "csv" and not csv_path:
        print("No CSV path/fixture found; pass --csv-path or use --source exchange")
        return 1

    print(
        f"Running BB solo tuning: {args.symbol} {args.timeframe} "
        f"{args.start}->{args.end} source={args.source} trials={args.max_trials}",
        flush=True,
    )

    async def on_progress(event) -> None:  # noqa: ANN001
        detail = getattr(event, "detail", "") or ""
        if event.stage == "done" or "bar" not in detail:
            print(
                f"[{event.phase}/{event.stage}] {event.current}/{event.total} {detail}",
                flush=True,
            )
            return
        if "bar " in detail:
            try:
                bar_part = detail.rsplit("bar ", 1)[-1]
                current_bar = int(bar_part.split("/", 1)[0])
            except (ValueError, IndexError):
                return
            if current_bar % 1000 == 0:
                print(
                    f"[{event.phase}/{event.stage}] {event.current}/{event.total} {detail}",
                    flush=True,
                )

    result = await run_optimization(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=start,
        end=end,
        source=args.source,
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
        max_parallel_trials=args.max_parallel_trials,
        on_progress=on_progress,
    )
    print(f"Completed {len(result.trials)} trials.", flush=True)
    print(f"best_valid={result.best_valid} holdout_valid={result.holdout_valid}", flush=True)
    print(f"selection_message={result.selection_message}", flush=True)
    if result.holdout_outcome:
        print(
            "holdout: "
            f"return_pct={result.holdout_outcome.get('return_pct')} "
            f"trades={result.holdout_outcome.get('total_trades')} "
            f"score={result.holdout_score}",
            flush=True,
        )
    _print_best(result)

    payload: dict[str, Any] = result_to_dict(result)
    candidate = result.best if result.best_valid and result.best is not None else None
    if candidate is None and result.fallback_trial is not None:
        candidate = result.fallback_trial

    if not args.skip_rescore and candidate is not None:
        print("\n=== Scorecard rescore of best params ===", flush=True)
        rescore = await evaluate_params_scorecard(
            candidate.params,
            start=start,
            end=end,
            symbol=args.symbol,
            timeframe=args.timeframe,
            holdout_ratio=args.holdout_ratio,
            train_ratio=args.train_ratio,
        )
        payload["scorecard_rescore"] = rescore
        print(f"scorecard_verdict={rescore.get('verdict')}", flush=True)
    elif args.skip_rescore:
        print("Skipping scorecard rescore (--skip-rescore).", flush=True)
    else:
        print("No candidate params to rescore.", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    print(f"Wrote {out}", flush=True)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
