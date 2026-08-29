#!/usr/bin/env python3
"""Run the managed long-core strategy through the real ValidationHarness and
check it reproduces the statistical research (docs/development/managed-long-core-findings.md).

Wires together the ported pieces:
  - CoreLongProvider (regime gate: BUY above sma_200, SELL — i.e. exit — below)
  - config/features.core_long.yaml (provides sma_200; keeps the global warm-up small)
  - execution long_only=True (SELL closes the long, never opens a short → cash)
  - execution exposure_pct_per_trade (notional-target sizing, not stop-distance risk)
  - RiskConfig.vol_target_atr_pct → FinalSignal.size_multiplier (vol-regime scaling)
  - a full risk_limits override (the default 5-consecutive-loss breaker bricks a
    whipsawy hold-the-core strategy mid-run)

The platform port is a coarser version of the research (spot = no leverage, so
the vol multiplier only de-risks; sizing is set at entry not rescaled daily;
real fills + whipsaw). It reproduces the *direction* of the result — roughly
half the max drawdown, better/comparable Sharpe and Calmar — not the exact
numbers.
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

from src.core.contracts.state import RiskLimits  # noqa: E402
from src.engine.config import (  # noqa: E402
    AggregationConfig,
    EngineConfig,
    FilterConfig,
    RiskConfig,
)
from src.execution.config import ValidationExecutionConfig  # noqa: E402
from src.features.config import load_features_config_file  # noqa: E402
from src.research.signal_evaluator import load_ohlcv  # noqa: E402
from src.validation.job_runner import run_validation_job  # noqa: E402

_ALL_PROVIDERS = (
    "ema_crossover",
    "rsi_divergence",
    "macd_momentum",
    "adx_trend_strength",
    "bollinger_reversion",
    "supertrend_trend",
    "volume_order_flow",
    "market_structure",
)


def _engine_config(vol_target_atr_pct: float, vol_target_cap: float) -> EngineConfig:
    return EngineConfig(
        aggregation=AggregationConfig(min_agreeing_providers=1, method="weighted_majority"),
        filter=FilterConfig(min_atr_pct=0.0, allowed_sessions=("ASIA", "EUROPE", "US", "OVERLAP")),
        risk=RiskConfig(
            max_daily_drawdown_pct=100.0,
            max_signals_per_day=100,
            min_confidence=0.6,
            min_risk_reward=0.0,
            max_open_positions=1,
            max_exposure_pct=100.0,
            vol_target_atr_pct=vol_target_atr_pct,
            vol_target_cap=vol_target_cap,
        ),
    )


def _perf_from_equity(equity: np.ndarray) -> dict:
    r = np.diff(equity) / equity[:-1]
    r = r[np.isfinite(r)]
    mean, std = float(r.mean()), float(r.std(ddof=1))
    dd = float((1 - equity / np.maximum.accumulate(equity)).max())
    ann_return = mean * 365
    return {
        "total_return_pct": round((equity[-1] / equity[0] - 1) * 100, 1),
        "ann_return_pct": round(ann_return * 100, 1),
        "sharpe": round(mean / std * (365**0.5), 3) if std else 0.0,
        "max_dd_pct": round(dd * 100, 1),
        "calmar": round(ann_return / dd, 3) if dd > 0 else None,
    }


def _mark_to_market_equity(
    df: pd.DataFrame, events: list, *, initial_capital: float = 10_000.0
) -> np.ndarray:
    """Daily mark-to-market equity from POSITION_OPENED/CLOSED events + the close series.

    ``compute_outcome_metrics`` steps equity only on *closed* trades, so it
    reports ~0 drawdown for a position held through a crash. This rebuilds the
    real curve.
    """
    from src.events.envelopes import ExecutionEventType

    ts = pd.to_datetime(df["timestamp"], utc=True)
    close = df["close"].to_numpy()
    opens = {
        pd.Timestamp(e.event_time).normalize(): e.payload["position"]
        for e in events
        if e.event_type == ExecutionEventType.POSITION_OPENED
    }
    closes = {
        pd.Timestamp(e.event_time).normalize(): e.payload
        for e in events
        if e.event_type == ExecutionEventType.POSITION_CLOSED
    }

    cash = initial_capital
    qty = 0.0
    sign = 0
    equity = np.empty(len(df))
    for i in range(len(df)):
        day = pd.Timestamp(ts.iloc[i]).normalize()
        if day in opens and qty == 0.0:
            pos = opens[day]
            qty = float(pos["quantity"])
            sign = 1 if pos["side"] == "LONG" else -1
            cash -= sign * qty * float(pos["entry_price"])
        equity[i] = cash + sign * qty * close[i]
        if day in closes and qty != 0.0:
            pl = closes[day]
            cash += sign * qty * float(pl["exit_price"])
            equity[i] = cash
            qty, sign = 0.0, 0
    return equity


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Managed long-core strategy validation run")
    parser.add_argument("--symbols", default="BTC/USDT,ETH/USDT")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument("--exposure-pct", type=float, default=100.0)
    parser.add_argument("--vol-target-atr-pct", type=float, default=2.5)
    parser.add_argument("--vol-target-cap", type=float, default=1.5)
    parser.add_argument("--sma", default="sma_150")
    args = parser.parse_args()

    features_config = load_features_config_file(
        _BACKEND.parent / "config" / "features.core_long.yaml"
    )
    exec_config = ValidationExecutionConfig(
        max_bars_in_trade=1_000_000,
        risk_pct_per_trade=1.0,
        long_only=True,
        exposure_pct_per_trade=args.exposure_pct,
    )
    overrides: dict[str, dict] = {p: {"enabled": False} for p in _ALL_PROVIDERS}
    overrides["core_long"] = {
        "enabled": True,
        "sma_indicator": args.sma,
        "confidence": 0.9,
        "min_confidence": 0.6,
        "regime_off_side": "SELL",
        "use_atr_stops": True,
        # Effectively disable SL/TP: the research strategy has no stops, it only
        # changes exposure on a regime flip. The far levels just satisfy the
        # engine's required stop_loss/take_profit fields.
        "sl_atr_mult": 1000.0,
        "tp_atr_mult": 1000.0,
    }

    for symbol in [s.strip() for s in args.symbols.split(",")]:
        df = await load_ohlcv(
            source="exchange",
            symbol=symbol,
            timeframe="1d",
            start=datetime.fromisoformat(args.start).replace(tzinfo=UTC),
            end=datetime.fromisoformat(args.end).replace(tzinfo=UTC),
        )
        result = await run_validation_job(
            symbol=symbol,
            timeframe="1d",
            start_date=args.start,
            end_date=args.end,
            source="exchange",
            persist_db=False,
            engine_config=_engine_config(args.vol_target_atr_pct, args.vol_target_cap),
            provider_overrides=overrides,
            execution_config=exec_config,
            features_config=features_config,
            # A hold-the-core strategy must not be bricked by the default
            # circuit breakers (5 consecutive losses, 50% exposure cap).
            risk_limits=RiskLimits(
                max_daily_drawdown_pct=100.0,
                max_open_positions=1,
                max_exposure_pct=100.0,
                max_consecutive_losses=100_000,
            ),
        )
        m = result.outcome_metrics or {}
        strat_eq = _mark_to_market_equity(df, list(result.events))
        bh_eq = 10_000.0 * (df["close"].to_numpy() / df["close"].to_numpy()[0])
        strat = _perf_from_equity(strat_eq)
        bh = _perf_from_equity(bh_eq)
        print(f"\n===== {symbol} 1d {args.start}..{args.end} =====", flush=True)
        print(f"  trades={m.get('total_trades')} win_rate={m.get('win_rate')}", flush=True)
        print(f"  strategy (mark-to-market): {strat}", flush=True)
        print(f"  buy & hold              : {bh}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
