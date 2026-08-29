#!/usr/bin/env python3
"""Does a wider carry basket beat the BTC+ETH carry?

The blended book's income leg is a delta-neutral carry on BTC + ETH. Alt-coin
perps (SOL, BNB, XRP, DOGE) tend to carry fatter, more persistent funding —
adding them should raise the basket's yield and, because their funding is not
perfectly correlated, smooth it. The cost is more tail risk per name (bigger
squeezes, thinner books), so the basket is equal-weighted and capped, not
concentrated in whatever pays most.

Statistical only, on real Binance funding. Compares:
  - BTC+ETH carry (current)
  - + SOL + BNB
  - + XRP + DOGE (6-name basket)
  - funding-tilted 6-name (weight up to 1.5x the names paying more, still capped)
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

from src.carry import load_funding_history, simulate_basis_carry
from src.carry.basis_carry import BasisCarryConfig

_ANN = 365


def _stats(daily: pd.Series) -> dict:
    d = daily.dropna()
    if len(d) < 120:
        return {"note": "insufficient"}
    eq = (1 + d).cumprod()
    mo = eq.resample("ME").last().pct_change().dropna()
    yrs = len(d) / _ANN
    return {
        "cagr": round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1),
        "vol": round(d.std(ddof=1) * np.sqrt(_ANN) * 100, 1),
        "sharpe": round(d.mean() / d.std(ddof=1) * np.sqrt(_ANN), 2),
        "maxdd": round((1 - eq / eq.cummax()).max() * 100, 2),
        "pos_mo": round((mo > 0).mean() * 100, 1),
        "worst_mo": round(mo.min() * 100, 2),
        "n_mo": len(mo),
    }


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Multi-asset carry basket screen")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2026-08-27")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)

    names = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT"]
    cfg = BasisCarryConfig()
    legs: dict[str, pd.Series] = {}
    gross: dict[str, float] = {}
    for sym in names:
        funding = load_funding_history(sym, start, end)
        legs[sym] = simulate_basis_carry(funding, cfg).daily_returns
        gross[sym] = funding["funding_rate"].mean() * 3 * _ANN * 100
        print(f"  {sym:12} gross funding ~{gross[sym]:.1f}%/yr (1x)", flush=True)

    frame = pd.DataFrame(legs)

    baskets = {
        "BTC+ETH (current)": frame[["BTC/USDT", "ETH/USDT"]].mean(axis=1),
        "+SOL+BNB (4)": frame[["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]].mean(axis=1),
        "6-name equal": frame.mean(axis=1),
    }
    # funding-tilted 6-name: weight ~ rank of trailing 30d gross funding, clipped [0.5, 1.5]
    trail = frame.rolling(30).mean()
    rank = trail.rank(axis=1, pct=True)
    tilt = (0.5 + rank).clip(0.5, 1.5)
    tilt = tilt.div(tilt.sum(axis=1), axis=0)
    baskets["6-name funding-tilted"] = (frame * tilt.shift(1)).sum(axis=1)

    print(
        f"\n{'basket':<24} {'CAGR%':>6} {'vol%':>5} {'Shrp':>5} {'maxDD%':>7} "
        f"{'+mo%':>6} {'worst mo%':>10} {'nMo':>4}",
        flush=True,
    )
    for label, series in baskets.items():
        s = _stats(series)
        if "note" in s:
            print(f"{label:<24} {s['note']}", flush=True)
            continue
        print(
            f"{label:<24} {s['cagr']:>6} {s['vol']:>5} {s['sharpe']:>5} {s['maxdd']:>7} "
            f"{s['pos_mo']:>6} {s['worst_mo']:>10} {s['n_mo']:>4}",
            flush=True,
        )

    cur = _stats(baskets["BTC+ETH (current)"])
    six = _stats(baskets["6-name equal"])
    print(
        f"\nVERDICT: 6-name basket CAGR {six['cagr']}% vs BTC+ETH {cur['cagr']}%, "
        f"Sharpe {six['sharpe']} vs {cur['sharpe']}, +months {six['pos_mo']}% vs {cur['pos_mo']}%. "
        f"{'Wider basket helps.' if six['sharpe'] >= cur['sharpe'] else 'No improvement.'}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
