#!/usr/bin/env python3
"""Calendar-year P&L for the managed long-core strategy vs buy & hold.

Runs the BTC and ETH legs through the real ValidationHarness (same wiring as
run_core_long_portfolio_validation), rebuilds each leg's mark-to-market equity,
forms the 50/50 book, and prints per-year return + intra-year max drawdown for
the strategy and for buy & hold.
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

from scripts.run_core_long_validation import (  # noqa: E402
    _ALL_PROVIDERS,
    _engine_config,
    _mark_to_market_equity,
)
from src.core.contracts.state import RiskLimits  # noqa: E402
from src.execution.config import ValidationExecutionConfig  # noqa: E402
from src.features.config import load_features_config_file  # noqa: E402
from src.research.signal_evaluator import load_ohlcv  # noqa: E402
from src.validation.job_runner import run_validation_job  # noqa: E402

_RISK_LIMITS = RiskLimits(
    max_daily_drawdown_pct=100.0,
    max_open_positions=1,
    max_exposure_pct=100.0,
    max_consecutive_losses=100_000,
)


def _year_stats(equity: pd.Series) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for year, group in equity.groupby(equity.index.year):
        vals = group.to_numpy()
        start = vals[0]
        prev_close = equity[equity.index.year == year - 1]
        base = prev_close.iloc[-1] if len(prev_close) else start
        ret = (vals[-1] / base - 1) * 100
        peak = np.maximum.accumulate(np.concatenate([[base], vals]))
        dd = float((1 - np.concatenate([[base], vals]) / peak).max()) * 100
        out[int(year)] = {"return_pct": round(ret, 1), "max_dd_pct": round(dd, 1)}
    return out


async def _leg(symbol: str, start: str, end: str, sma: str, atr_pct: float, cap: float, feats):
    df = await load_ohlcv(
        source="exchange",
        symbol=symbol,
        timeframe="1d",
        start=datetime.fromisoformat(start).replace(tzinfo=UTC),
        end=datetime.fromisoformat(end).replace(tzinfo=UTC),
    )
    overrides = {p: {"enabled": False} for p in _ALL_PROVIDERS}
    overrides["core_long"] = {
        "enabled": True,
        "sma_indicator": sma,
        "confidence": 0.9,
        "min_confidence": 0.6,
        "regime_off_side": "SELL",
        "use_atr_stops": True,
        "sl_atr_mult": 1000.0,
        "tp_atr_mult": 1000.0,
    }
    result = await run_validation_job(
        symbol=symbol,
        timeframe="1d",
        start_date=start,
        end_date=end,
        source="exchange",
        persist_db=False,
        retain_events=True,
        engine_config=_engine_config(atr_pct, cap),
        provider_overrides=overrides,
        execution_config=ValidationExecutionConfig(
            max_bars_in_trade=1_000_000,
            risk_pct_per_trade=1.0,
            long_only=True,
            exposure_pct_per_trade=100.0,
        ),
        features_config=feats,
        risk_limits=_RISK_LIMITS,
    )
    ts = pd.to_datetime(df["timestamp"], utc=True)
    strat = pd.Series(_mark_to_market_equity(df, list(result.events)), index=ts)
    bh = pd.Series(10_000.0 * df["close"].to_numpy() / df["close"].to_numpy()[0], index=ts)
    return strat, bh


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Managed long-core annual P&L breakdown")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument("--sma", default="sma_150")
    parser.add_argument("--vol-target-atr-pct", type=float, default=2.5)
    parser.add_argument("--vol-target-cap", type=float, default=1.5)
    args = parser.parse_args()
    feats = load_features_config_file(_BACKEND.parent / "config" / "features.core_long.yaml")

    legs = {}
    for symbol in ("BTC/USDT", "ETH/USDT"):
        strat, bh = await _leg(
            symbol,
            args.start,
            args.end,
            args.sma,
            args.vol_target_atr_pct,
            args.vol_target_cap,
            feats,
        )
        legs[symbol] = (strat, bh)

    idx = legs["BTC/USDT"][0].index.intersection(legs["ETH/USDT"][0].index)

    def book(which: int) -> pd.Series:
        b = legs["BTC/USDT"][which].reindex(idx).ffill()
        e = legs["ETH/USDT"][which].reindex(idx).ffill()
        return (0.5 * b / b.iloc[0] + 0.5 * e / e.iloc[0]) * 10_000.0

    rows = {
        "BTC strat": _year_stats(legs["BTC/USDT"][0]),
        "BTC b&h": _year_stats(legs["BTC/USDT"][1]),
        "ETH strat": _year_stats(legs["ETH/USDT"][0]),
        "ETH b&h": _year_stats(legs["ETH/USDT"][1]),
        "50/50 PORTFOLIO": _year_stats(book(0)),
        "50/50 b&h": _year_stats(book(1)),
    }
    years = sorted({y for r in rows.values() for y in r})

    print(f"\ncalendar-year return %  (intra-year maxDD in parens)  {args.start}..{args.end}\n")
    header = f"{'':<17}" + "".join(f"{y:>16}" for y in years)
    print(header, flush=True)
    for name, data in rows.items():
        cells = []
        for y in years:
            if y in data:
                cells.append(f"{data[y]['return_pct']:>+8.0f} ({data[y]['max_dd_pct']:>3.0f}%)")
            else:
                cells.append(f"{'-':>16}")
        print(f"{name:<17}" + "".join(cells), flush=True)

    # rolling 12-month returns (every start date), portfolio vs 50/50 b&h
    print("\nrolling 12-month return % (all start dates):\n", flush=True)
    for name, series in (("50/50 PORTFOLIO", book(0)), ("50/50 b&h", book(1))):
        s = series.resample("1D").ffill()
        roll = (s / s.shift(365) - 1) * 100
        roll = roll.dropna()
        neg = (roll < 0).mean() * 100
        print(
            f"  {name:<17} min={roll.min():>+7.0f}  p25={roll.quantile(0.25):>+7.0f}  "
            f"median={roll.median():>+7.0f}  p75={roll.quantile(0.75):>+7.0f}  "
            f"max={roll.max():>+7.0f}  | share of windows negative: {neg:.0f}%",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
