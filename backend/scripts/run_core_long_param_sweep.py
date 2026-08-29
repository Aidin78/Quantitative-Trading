#!/usr/bin/env python3
"""Parameter sweep for the ported managed long-core strategy.

Item 3 of the "remaining (optional)" list in
docs/development/managed-long-core-findings.md: confirm the hand-picked
``--vol-target-atr-pct 3.0`` / ``sma_200`` are not a lucky point but sit in a
consistent neighbourhood — the same robustness bar the statistical research
held itself to (a coherent parameter region, not scattered wins).

Sweeps ``sma_indicator ∈ {sma_100, sma_150, sma_200}`` ×
``vol_target_atr_pct ∈ {0, 2.0, 2.5, 3.0, 3.5, 4.0}`` (0 = regime gate only,
no vol scaling) on BTC and ETH daily, and prints strategy-vs-buy&hold
Sharpe / MaxDD / Calmar for every cell.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

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

_SMA = ("sma_100", "sma_150", "sma_200")
_ATR_PCT = (0.0, 2.0, 2.5, 3.0, 3.5, 4.0)


async def _one(symbol, df, features_config, sma, atr_pct, cap, start, end):
    exec_config = ValidationExecutionConfig(
        max_bars_in_trade=1_000_000,
        risk_pct_per_trade=1.0,
        long_only=True,
        exposure_pct_per_trade=100.0,
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
        engine_config=_engine_config(atr_pct, cap),
        provider_overrides=overrides,
        execution_config=exec_config,
        features_config=features_config,
        risk_limits=RiskLimits(
            max_daily_drawdown_pct=100.0,
            max_open_positions=1,
            max_exposure_pct=100.0,
            max_consecutive_losses=100_000,
        ),
    )
    eq = _mark_to_market_equity(df, list(result.events))
    return _perf_from_equity(eq), (result.outcome_metrics or {}).get("total_trades")


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Managed long-core parameter sweep")
    parser.add_argument("--symbols", default="BTC/USDT,ETH/USDT")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument("--vol-target-cap", type=float, default=1.5)
    args = parser.parse_args()

    features_config = load_features_config_file(
        _BACKEND.parent / "config" / "features.core_long.yaml"
    )

    for symbol in [s.strip() for s in args.symbols.split(",")]:
        df = await load_ohlcv(
            source="exchange",
            symbol=symbol,
            timeframe="1d",
            start=datetime.fromisoformat(args.start).replace(tzinfo=UTC),
            end=datetime.fromisoformat(args.end).replace(tzinfo=UTC),
        )
        bh = _perf_from_equity(10_000.0 * (df["close"].to_numpy() / df["close"].to_numpy()[0]))
        print(f"\n===== {symbol} 1d {args.start}..{args.end} =====", flush=True)
        print(
            f"  buy & hold: sharpe {bh['sharpe']}  maxDD {bh['max_dd_pct']}%  "
            f"calmar {bh['calmar']}  ret {bh['total_return_pct']}%",
            flush=True,
        )
        print(
            f"  {'sma':<9} {'atr%':>5} {'trades':>7} {'sharpe':>7} {'maxDD%':>7} "
            f"{'calmar':>7} {'ret%':>9}",
            flush=True,
        )
        for sma in _SMA:
            for atr_pct in _ATR_PCT:
                perf, trades = await _one(
                    symbol,
                    df,
                    features_config,
                    sma,
                    atr_pct,
                    args.vol_target_cap,
                    args.start,
                    args.end,
                )
                print(
                    f"  {sma:<9} {atr_pct:>5.1f} {str(trades):>7} {perf['sharpe']:>7} "
                    f"{perf['max_dd_pct']:>7} {str(perf['calmar']):>7} "
                    f"{perf['total_return_pct']:>9}",
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
