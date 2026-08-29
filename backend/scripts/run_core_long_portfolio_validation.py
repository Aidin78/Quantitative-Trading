#!/usr/bin/env python3
"""Validate the BTC+ETH managed long-core *portfolio* on the platform.

The statistical screen (run_core_long_portfolio_research.py) showed a 50/50
book of the two managed legs beats the single-asset version on every risk
metric — lower max drawdown than either leg alone (diversification), higher
Sharpe — and at buy&hold-equivalent volatility it beats buy&hold on both
return and drawdown.

The platform needs no multi-asset runtime for this: the portfolio is just two
independent instances of the ported CoreLongProvider strategy with capital
split 50/50 at the account level. This script runs each leg through the real
ValidationHarness (reusing run_core_long_validation's wiring), rebuilds each
leg's mark-to-market equity, combines them 50/50, and reports the book vs a
50/50 BTC+ETH buy&hold.
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
    _perf_from_equity,
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


async def _leg_equity(
    symbol: str, start: str, end: str, sma: str, atr_pct: float, cap: float, features_config
) -> tuple[np.ndarray, np.ndarray, dict]:
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
        features_config=features_config,
        risk_limits=_RISK_LIMITS,
    )
    strat_eq = _mark_to_market_equity(df, list(result.events))
    bh_eq = 10_000.0 * (df["close"].to_numpy() / df["close"].to_numpy()[0])
    ts = pd.to_datetime(df["timestamp"], utc=True).dt.normalize().to_numpy()
    return (
        pd.Series(strat_eq, index=ts),
        pd.Series(bh_eq, index=ts),
        result.outcome_metrics or {},
    )


async def _run() -> int:
    parser = argparse.ArgumentParser(description="BTC+ETH managed-core portfolio validation")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument("--sma", default="sma_150")
    parser.add_argument("--vol-target-atr-pct", type=float, default=2.5)
    parser.add_argument("--vol-target-cap", type=float, default=1.5)
    args = parser.parse_args()

    features_config = load_features_config_file(
        _BACKEND.parent / "config" / "features.core_long.yaml"
    )

    legs = {}
    for symbol in ("BTC/USDT", "ETH/USDT"):
        strat, bh, m = await _leg_equity(
            symbol,
            args.start,
            args.end,
            args.sma,
            args.vol_target_atr_pct,
            args.vol_target_cap,
            features_config,
        )
        legs[symbol] = {"strat": strat, "bh": bh, "trades": m.get("total_trades")}

    idx = legs["BTC/USDT"]["strat"].index.intersection(legs["ETH/USDT"]["strat"].index)

    # normalise each leg to 1.0 at the first shared bar, then 50/50 book
    def _book(key: str) -> np.ndarray:
        b = legs["BTC/USDT"][key].reindex(idx).ffill()
        e = legs["ETH/USDT"][key].reindex(idx).ffill()
        return (0.5 * b / b.iloc[0] + 0.5 * e / e.iloc[0]).to_numpy() * 10_000.0

    port = _perf_from_equity(_book("strat"))
    bh5050 = _perf_from_equity(_book("bh"))
    btc = _perf_from_equity((legs["BTC/USDT"]["strat"].reindex(idx).ffill()).to_numpy())
    eth = _perf_from_equity((legs["ETH/USDT"]["strat"].reindex(idx).ffill()).to_numpy())

    print(f"\n===== managed long-core portfolio {args.start}..{args.end} =====", flush=True)
    btc_t, eth_t = legs["BTC/USDT"]["trades"], legs["ETH/USDT"]["trades"]
    print(f"  BTC leg trades={btc_t}  ETH leg trades={eth_t}")
    print(f"  BTC leg (mtm)      : {btc}", flush=True)
    print(f"  ETH leg (mtm)      : {eth}", flush=True)
    print(f"  50/50 PORTFOLIO    : {port}", flush=True)
    print(f"  50/50 buy & hold   : {bh5050}", flush=True)
    better_dd = port["max_dd_pct"] < min(btc["max_dd_pct"], eth["max_dd_pct"])
    print(
        f"\n  portfolio maxDD {port['max_dd_pct']}% "
        f"{'<' if better_dd else '>='} best single leg "
        f"{min(btc['max_dd_pct'], eth['max_dd_pct'])}%  "
        f"({'diversifies' if better_dd else 'no benefit'})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
