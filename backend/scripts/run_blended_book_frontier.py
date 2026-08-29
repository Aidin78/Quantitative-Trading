#!/usr/bin/env python3
"""How close can a balanced carry+core book get to 'positive every month, 7-8%'?

Answers the user's revised target by mapping the real frontier: sweep the
carry/core weight and an optional target-volatility overlay (the standard way
to dial a return target while capping drawdown), and for every point report
CAGR, max drawdown, % of months positive, median month, and worst month.

Books:
  - carry  = delta-neutral basis carry, BTC+ETH equal weight (from
    run_basis_carry_research._carry_daily)
  - core   = managed long-core proxy, BTC+ETH equal weight
  - blend  = w*carry + (1-w)*core, optionally scaled so trailing realised vol
    hits a target (leverage capped so a bad day can't wipe the book)

Everything statistical, net of costs already in the leg builders.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from scripts.run_basis_carry_research import (  # noqa: E402
    _carry_daily,
    _managed_core_daily,
    _stats,
)
from scripts.run_funding_signal_research import _download_funding  # noqa: E402

TARGET_MONTHLY = 0.075  # the user's ask, for reference in the verdict
LEVERAGE_CAP = 3.0


def _vol_target(daily: pd.Series, target_ann_vol: float, *, window: int = 30) -> pd.Series:
    """Scale each day's return so trailing realised vol ~= target (lev capped)."""
    realised = daily.rolling(window).std(ddof=1) * (365**0.5)
    lev = (target_ann_vol / realised).clip(upper=LEVERAGE_CAP).shift(1).fillna(1.0)
    return daily * lev


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Carry+core blended-book frontier")
    parser.add_argument("--symbols", default="BTC/USDT,ETH/USDT")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2026-08-27")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    symbols = [s.strip() for s in args.symbols.split(",")]

    carry_legs = {}
    for symbol in symbols:
        f = _download_funding(symbol, start, end)
        f = f[(f["timestamp"] >= pd.Timestamp(start)) & (f["timestamp"] <= pd.Timestamp(end))]
        carry_legs[symbol] = _carry_daily(f, conditional=False)
    carry = pd.DataFrame(carry_legs).dropna(how="all").mean(axis=1)
    core_legs = {s: await _managed_core_daily(s, start, end) for s in symbols}
    core = pd.DataFrame(core_legs).dropna(how="all").mean(axis=1)

    both = pd.DataFrame({"carry": carry, "core": core}).dropna()

    rows: list[dict] = []
    # 1) raw weight sweep, no vol overlay
    for w in (0.9, 0.8, 0.7, 0.6, 0.5):
        blend = w * both["carry"] + (1 - w) * both["core"]
        rows.append({"cfg": f"{int(w * 100)}/{int((1 - w) * 100)} raw", **_stats(blend, "")})
    # 2) 70/30 base, scaled to a target annual vol
    base = 0.7 * both["carry"] + 0.3 * both["core"]
    for tv in (0.08, 0.12, 0.18, 0.25, 0.40):
        rows.append({"cfg": f"70/30 @ {int(tv * 100)}% vol", **_stats(_vol_target(base, tv), "")})

    print(
        f"\n{'config':<20} {'CAGR%':>7} {'vol%':>6} {'Sharpe':>7} {'maxDD%':>7} "
        f"{'mo.med%':>8} {'mo.min%':>8} {'+months%':>9}",
        flush=True,
    )
    for r in rows:
        if "note" in r:
            print(f"{r['cfg']:<20} {r['note']}", flush=True)
            continue
        print(
            f"{r['cfg']:<20} {r['cagr_pct']:>7} {r['vol_pct']:>6} {r['sharpe']:>7} "
            f"{r['max_dd_pct']:>7} {r['monthly_median_pct']:>8} {r['monthly_min_pct']:>8} "
            f"{r['pct_months_positive']:>9}",
            flush=True,
        )

    best = max(
        (r for r in rows if "note" not in r),
        key=lambda r: (r["pct_months_positive"] >= 75) * 100 + r["sharpe"],
    )
    need_lev = (
        TARGET_MONTHLY / (best["monthly_median_pct"] / 100)
        if best["monthly_median_pct"]
        else np.inf
    )
    print("\nVERDICT:", flush=True)
    print(
        f"  best 'balanced + mostly-positive' point: {best['cfg']} — "
        f"~{best['cagr_pct']:.0f}%/yr ({best['monthly_median_pct']:.1f}%/mo median), "
        f"{best['pct_months_positive']:.0f}% of months green, worst month "
        f"{best['monthly_min_pct']:.1f}%, maxDD {best['max_dd_pct']:.0f}%.",
        flush=True,
    )
    print(
        f"  reaching the 7-8%/month ask from there needs ~{need_lev:.0f}x more leverage, "
        f"which scales the worst month to ~{best['monthly_min_pct'] * need_lev:.0f}% and "
        f"destroys 'balanced'. 7-8%/month with mostly-positive months is not on the frontier.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
