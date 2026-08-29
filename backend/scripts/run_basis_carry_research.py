#!/usr/bin/env python3
"""Can a delta-neutral basis-carry trade deliver *steady monthly* returns?

The managed long-core strategy is directional — great years and small-loss
years, but it can't promise a positive month. The one strategy class in crypto
that historically pays a smooth, mostly-positive stream is the **cash-and-carry
basis trade**: hold spot, short the same notional of the perpetual future
(delta-neutral), and collect the funding rate that perp longs pay perp shorts.

This is a statistical screen (no engine, no execution) over Binance BTC and
ETH funding history. It measures the realistic monthly profile:
  - always-on carry vs carry-only-when-funding-positive
  - net of a per-rebalance cost and a haircut for capital inefficiency
    (spot + isolated perp margin ties up ~1.6x capital for 1x carry)
  - monthly return series, % positive months, worst month, annualised, Sharpe

Look-ahead: funding print stamped at t is earned over [t, t+8h]; the position
for that interval is decided from funding known at or before t.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from scripts.run_funding_signal_research import _download_funding  # noqa: E402
from src.research.signal_evaluator import load_ohlcv  # noqa: E402

ANN = 365
# Managed long-core proxy params (docs/development/managed-long-core-findings.md)
CORE_SMA_N = 150
CORE_VOL_W = 30
CORE_TARGET_VOL = 0.5
CORE_CAP = 1.5

# Capital haircut: 1x delta-neutral carry needs spot notional + perp margin.
# At ~3x perp leverage that is 1.0 + 0.33 ~= 1.33x; keep a conservative 1.6x
# buffer so a perp drawdown doesn't force a deleverage.
CAPITAL_MULTIPLIER = 1.6
# Round-trip cost each time we flip the position on/off (spot + perp taker).
FLIP_COST = 0.0008  # 8 bps


def _monthly(daily: pd.Series) -> pd.Series:
    eq = (1.0 + daily.fillna(0.0)).cumprod()
    return eq.resample("ME").last().pct_change().dropna()


def _stats(daily: pd.Series, label: str) -> dict:
    d = daily.dropna()
    if len(d) < 90:
        return {"label": label, "note": "insufficient data"}
    eq = (1.0 + d).cumprod()
    yrs = len(d) / 365.0
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    mdd = float((1 - eq / eq.cummax()).max())
    mo = _monthly(d)
    sharpe = d.mean() / d.std() * (365**0.5) if d.std() > 0 else 0.0
    return {
        "label": label,
        "cagr_pct": round(cagr * 100, 1),
        "vol_pct": round(d.std() * (365**0.5) * 100, 1),
        "sharpe": round(sharpe, 2),
        "max_dd_pct": round(mdd * 100, 2),
        "monthly_median_pct": round(mo.median() * 100, 2),
        "monthly_min_pct": round(mo.min() * 100, 2),
        "monthly_max_pct": round(mo.max() * 100, 2),
        "pct_months_positive": round((mo > 0).mean() * 100, 1),
        "n_months": int(len(mo)),
        "worst_3_months": [round(x * 100, 2) for x in mo.nsmallest(3)],
    }


def _carry_daily(funding: pd.DataFrame, *, conditional: bool, trail_prints: int = 3) -> pd.Series:
    """Daily return of the delta-neutral carry, in % of the 1x notional.

    funding_rate is per 8h. A day has up to three prints; their sum is the
    day's gross carry. `conditional` holds the position only when the trailing
    funding sum is positive (decided from prior prints => no look-ahead).
    """
    f = funding.copy()
    f["day"] = f["timestamp"].dt.floor("D")
    daily_gross = f.groupby("day")["funding_rate"].sum()
    daily_gross.index = pd.DatetimeIndex(daily_gross.index)

    if conditional:
        trail = f.set_index("timestamp")["funding_rate"].rolling(f"{trail_prints * 8}h").sum()
        # position for day D decided from the last print strictly before D 00:00
        decision = trail.resample("D").last().shift(1)
        hold = (decision > 0).reindex(daily_gross.index).fillna(False)
    else:
        hold = pd.Series(True, index=daily_gross.index)

    gross = daily_gross.where(hold, 0.0)
    flips = hold.astype(int).diff().abs().fillna(0.0)
    net_notional = gross - flips * FLIP_COST
    return net_notional / CAPITAL_MULTIPLIER


async def _managed_core_daily(symbol: str, start: datetime, end: datetime) -> pd.Series:
    """Statistical proxy for the managed long-core leg: regime gate x vol target."""
    df = await load_ohlcv(source="exchange", symbol=symbol, timeframe="1d", start=start, end=end)
    df = df.copy()
    df["ts"] = pd.to_datetime(df["timestamp"], utc=True)
    close = df.set_index("ts")["close"]
    ret = close.pct_change()
    gate = (close > close.rolling(CORE_SMA_N).mean()).fillna(False).astype(float)
    vol = ret.rolling(CORE_VOL_W).std(ddof=1)
    size = (CORE_TARGET_VOL / (ANN**0.5) / vol).clip(lower=0.0, upper=CORE_CAP)
    w = (gate * size).shift(1)
    turn = w.diff().abs().fillna(w.abs())
    return (w * ret - turn * 0.0008).dropna()


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Delta-neutral basis-carry screen (statistical)")
    parser.add_argument("--symbols", default="BTC/USDT,ETH/USDT")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2026-08-27")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    symbols = [s.strip() for s in args.symbols.split(",")]

    legs_always: dict[str, pd.Series] = {}
    legs_cond: dict[str, pd.Series] = {}
    for symbol in symbols:
        funding = _download_funding(symbol, start, end)
        funding = funding[
            (funding["timestamp"] >= pd.Timestamp(start))
            & (funding["timestamp"] <= pd.Timestamp(end))
        ]
        legs_always[symbol] = _carry_daily(funding, conditional=False)
        legs_cond[symbol] = _carry_daily(funding, conditional=True)
        gross_ann = funding["funding_rate"].mean() * 3 * 365 * 100
        print(
            f"{symbol}: {len(funding)} funding prints, "
            f"mean {funding['funding_rate'].mean() * 100:.4f}%/8h  (~{gross_ann:.1f}%/yr gross 1x)",
            flush=True,
        )

    def _book(legs: dict[str, pd.Series]) -> pd.Series:
        df = pd.DataFrame(legs).dropna(how="all")
        return df.mean(axis=1)

    results = []
    for symbol in symbols:
        results.append(_stats(legs_always[symbol], f"{symbol} carry always-on"))
        results.append(_stats(legs_cond[symbol], f"{symbol} carry funding>0"))
    carry_book = _book(legs_always)
    results.append(_stats(carry_book, "BOOK carry always-on"))
    results.append(_stats(_book(legs_cond), "BOOK carry funding>0"))

    # managed long-core book (statistical proxy) + carry/core blends
    core_legs = {s: await _managed_core_daily(s, start, end) for s in symbols}
    core_book = pd.DataFrame(core_legs).dropna(how="all").mean(axis=1)
    results.append(_stats(core_book, "BOOK managed long-core"))
    for w_carry in (0.7, 0.5, 0.3):
        blend = pd.DataFrame({"c": carry_book, "m": core_book}).dropna()
        mixed = w_carry * blend["c"] + (1 - w_carry) * blend["m"]
        results.append(
            _stats(mixed, f"BLEND {int(w_carry * 100)}% carry / {int((1 - w_carry) * 100)}% core")
        )

    print(
        f"\n{'strategy':<34} {'cagr%':>7} {'vol%':>6} {'shrp':>5} {'maxDD%':>7} "
        f"{'mo.med%':>8} {'mo.min%':>8} {'+mo%':>6} {'nMo':>4}",
        flush=True,
    )
    for r in results:
        if "note" in r:
            print(f"{r['label']:<34} {r['note']}", flush=True)
            continue
        print(
            f"{r['label']:<34} {r['cagr_pct']:>7} {r['vol_pct']:>6} {r['sharpe']:>5} "
            f"{r['max_dd_pct']:>7} {r['monthly_median_pct']:>8} {r['monthly_min_pct']:>8} "
            f"{r['pct_months_positive']:>6} {r['n_months']:>4}",
            flush=True,
        )
        print(f"{'   worst 3 months %:':<34} {r['worst_3_months']}", flush=True)

    carry = next(r for r in results if r["label"] == "BOOK carry always-on")
    print("\nVERDICT:", flush=True)
    print(
        f"  pure carry: ~{carry['cagr_pct']}%/yr, {carry['pct_months_positive']}% months "
        f"positive, worst month {carry['monthly_min_pct']}%, maxDD {carry['max_dd_pct']}% "
        f"-- i.e. ~{carry['cagr_pct'] / 12:.1f}%/month, steady.\n"
        f"  '15%/month' (=435%/yr, zero down months) is not achievable by any legitimate "
        f"strategy. The real choice is consistency (carry) vs growth (core) vs a blend.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
