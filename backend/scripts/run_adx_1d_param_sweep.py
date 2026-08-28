#!/usr/bin/env python3
"""Follow-up on docs/development/provider-edge-htf-experiment-plan.md's recommended next
action: "bounded follow-up on 1d ADX only ... light Optuna on adx_* params only".

Background: the 1d provider edge scorecard (backend/data/provider_edge_scorecard_1d.json)
found solo_ADX_agree1 keep-verdict on BTC/USDT 1d (train +6.19%/21 trades, holdout
+0.45%/16 trades) using the platform's real ValidationHarness/DecisionEngine (not a
research-only approximation) -- the only keep across 1h/4h/1d in the whole investigation.
The plan explicitly flagged this as a fragile result (samples barely clear the keep floors)
and recommended checking sensitivity to the ADX parameters (min_adx, min_di_spread,
adx_period) before treating it as a real finding, rather than a lucky default.

Network access to download a longer BTC history or ETH data is unavailable in this
environment (tested, hung indefinitely) -- this sweep is bounded to the same cached
2025-01-01 -> 2026-07-18 BTC/USDT 1d range (565 bars) the original scorecard used, reusing
its exact train/test/holdout split (split_scorecard_windows) and keep/watch/drop rule
(verdict_for_windows) so results are directly comparable to the original finding, not a
new methodology.

Real ValidationHarness runs via evaluate_params_scorecard -- this is NOT a lightweight
research approximation; every point in the grid is a full backtest through the real
DecisionEngine/ExecutionEngine, same as the original scorecard entry.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.validation.provider_edge_scorecard import (  # noqa: E402
    BASE_PARAMS,
    evaluate_params_scorecard,
)

# Centered on the scorecard's fixed defaults (adx_period=14, min_adx=25,
# min_di_spread=5) -- a bounded neighborhood, not a wide/fishing grid, per the
# plan's "bounded follow-up" instruction.
ADX_PERIOD_GRID = (10, 14)
MIN_ADX_GRID = (20.0, 25.0, 30.0)
MIN_DI_SPREAD_GRID = (3.0, 5.0, 8.0)


def _int_list(raw: str) -> tuple[int, ...]:
    return tuple(int(x) for x in raw.split(","))


def _float_list(raw: str) -> tuple[float, ...]:
    return tuple(float(x) for x in raw.split(","))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bounded ADX param sweep on BTC/USDT 1d")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2026-07-18")
    parser.add_argument("--adx-periods", type=_int_list, default=ADX_PERIOD_GRID)
    parser.add_argument("--min-adx", type=_float_list, default=MIN_ADX_GRID)
    parser.add_argument("--min-di-spread", type=_float_list, default=MIN_DI_SPREAD_GRID)
    parser.add_argument(
        "--out",
        default=str(_BACKEND / "data" / "adx_1d_param_sweep_result.json"),
    )
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)

    grid = list(itertools.product(args.adx_periods, args.min_adx, args.min_di_spread))
    print(f"Sweeping {len(grid)} ADX parameter combinations on {args.symbol} {args.timeframe}")
    print(
        f"adx_period={args.adx_periods} min_adx={args.min_adx} "
        f"min_di_spread={args.min_di_spread}"
    )

    results: list[dict] = []
    for adx_period, min_adx, min_di_spread in grid:
        params = {
            **BASE_PARAMS,
            "adx_enabled": 1,
            "min_agreeing_providers": 1,
            "adx_period": adx_period,
            "min_adx": min_adx,
            "min_di_spread": min_di_spread,
        }
        label = f"adx_period={adx_period} min_adx={min_adx} min_di_spread={min_di_spread}"
        print(f"\n=== {label} ===", flush=True)
        try:
            payload = await evaluate_params_scorecard(
                params,
                start=start,
                end=end,
                symbol=args.symbol,
                timeframe=args.timeframe,
            )
        except Exception as exc:  # noqa: BLE001 - one bad combo must not abort the sweep
            print(f"  ERROR ({type(exc).__name__}): {exc}", flush=True)
            results.append(
                {
                    "adx_period": adx_period,
                    "min_adx": min_adx,
                    "min_di_spread": min_di_spread,
                    "verdict": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "train": {},
                    "test": {},
                    "holdout": {},
                }
            )
            continue
        row = payload["result"]
        train = row.get("train") or {}
        test = row.get("test") or {}
        holdout = row.get("holdout") or {}
        print(
            f"  verdict={payload['verdict']}  "
            f"train(ret={train.get('return_pct')}, n={train.get('total_trades')})  "
            f"test(ret={test.get('return_pct')}, n={test.get('total_trades')})  "
            f"holdout(ret={holdout.get('return_pct')}, n={holdout.get('total_trades')})",
            flush=True,
        )
        results.append(
            {
                "adx_period": adx_period,
                "min_adx": min_adx,
                "min_di_spread": min_di_spread,
                "verdict": payload["verdict"],
                "train": train,
                "test": test,
                "holdout": holdout,
            }
        )

    keep_count = sum(1 for r in results if r["verdict"] == "keep")
    watch_count = sum(1 for r in results if r["verdict"] == "watch")
    drop_count = sum(1 for r in results if r["verdict"] == "drop")
    error_count = sum(1 for r in results if r["verdict"] == "error")
    print(
        f"\n=== SUMMARY: {keep_count} keep / {watch_count} watch / {drop_count} drop "
        f"/ {error_count} error out of {len(results)} ===",
        flush=True,
    )
    for r in results:
        if r["verdict"] != "drop":
            print(
                f"  {r['verdict']}: adx_period={r['adx_period']} min_adx={r['min_adx']} "
                f"min_di_spread={r['min_di_spread']}  "
                f"train_ret={r['train'].get('return_pct')} "
                f"holdout_ret={r['holdout'].get('return_pct')}",
                flush=True,
            )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "start": args.start,
                "end": args.end,
                "grid": {
                    "adx_period": list(args.adx_periods),
                    "min_adx": list(args.min_adx),
                    "min_di_spread": list(args.min_di_spread),
                },
                "results": results,
                "summary": {
                    "keep": keep_count,
                    "watch": watch_count,
                    "drop": drop_count,
                    "error": error_count,
                },
            },
            default=str,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {out}", flush=True)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
