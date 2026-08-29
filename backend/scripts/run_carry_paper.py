#!/usr/bin/env python3
"""Paper run of the carry leg: the full runner chain over historical data.

Drives CarryRunner (decide -> plan -> PaperCarryExecutor -> apply -> accrue)
over HistoricalPerpProvider snapshots for BTC and ETH, and checks the result
matches simulate_basis_carry (the closed-form backtest). If they agree the
runner/position-manager chain is faithful and the same loop can be pointed at
a live executor.
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

from src.carry import (
    CarryManagerConfig,
    CarryRunner,
    HistoricalPerpProvider,
    PaperCarryExecutor,
    load_funding_history,
    simulate_basis_carry,
)
from src.research.signal_evaluator import load_ohlcv


def _perf(equity: np.ndarray) -> dict:
    r = np.diff(equity) / equity[:-1]
    r = r[np.isfinite(r)]
    eq = equity / equity[0]
    yrs = len(r) / 365
    mo = pd.Series(eq).groupby(np.arange(len(eq)) // 30).last().pct_change().dropna()
    return {
        "total_ret_pct": round((equity[-1] / equity[0] - 1) * 100, 1),
        "cagr_pct": round((eq[-1] ** (1 / yrs) - 1) * 100, 1),
        "sharpe": round(r.mean() / r.std() * (365**0.5), 2) if r.std() else 0.0,
        "maxdd_pct": round(float((1 - eq / np.maximum.accumulate(eq)).max()) * 100, 2),
        "pos_month_pct": round((mo > 0).mean() * 100, 1),
    }


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Carry leg paper run")
    parser.add_argument("--symbols", default="BTC/USDT,ETH/USDT")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument("--capital", type=float, default=10_000.0)
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    cfg = CarryManagerConfig(capital_multiplier=1.5, min_trailing_funding_8h=-1.0)

    books = []
    for symbol in [s.strip() for s in args.symbols.split(",")]:
        ohlcv = await load_ohlcv(
            source="exchange", symbol=symbol, timeframe="1d", start=start, end=end
        )
        funding = load_funding_history(symbol, start, end)
        provider = HistoricalPerpProvider(symbol, ohlcv, funding)

        runner = CarryRunner(
            PaperCarryExecutor(taker_bps=4.0, slippage_bps=3.0),
            initial_capital=args.capital,
            config=cfg,
        )
        runner.run(provider.snapshots())
        eq = np.array(runner.log.equity)
        p = _perf(eq)

        bt = simulate_basis_carry(funding)
        bt_eq = args.capital * (1 + bt.daily_returns).cumprod().to_numpy()
        bp = _perf(np.concatenate([[args.capital], bt_eq]))

        n_resize = runner.log.actions.count("resize")
        n_reb = runner.log.actions.count("rebalance")
        print(f"\n=== {symbol} ===", flush=True)
        print(f"  runner (paper)   : {p}   resizes={n_resize} rebalances={n_reb}", flush=True)
        print(f"  simulate_basis_carry: {bp}", flush=True)
        print(
            f"  match: total return {p['total_ret_pct']}% vs {bp['total_ret_pct']}% "
            f"(diff {p['total_ret_pct'] - bp['total_ret_pct']:+.1f}pp)",
            flush=True,
        )
        books.append(pd.Series(eq, index=pd.to_datetime(runner.log.ts)))

    if len(books) > 1:
        idx = books[0].index.intersection(books[1].index)
        book = sum(b.reindex(idx).ffill() / b.reindex(idx).ffill().iloc[0] for b in books) / len(
            books
        )
        print(
            f"\n=== equal-weight carry book ===\n  {_perf(book.to_numpy() * args.capital)}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
