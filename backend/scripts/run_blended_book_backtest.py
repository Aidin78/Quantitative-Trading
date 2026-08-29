#!/usr/bin/env python3
"""Full backtest of the carry + managed-core blended book.

The recommended deployable book (docs/development/basis-carry-findings.md):
70% delta-neutral basis carry (BTC+ETH), 30% managed long-core (BTC+ETH),
scaled to a ~13% annual vol target.

  - carry leg  : src.carry.simulate_basis_carry on real Binance funding
  - core leg   : the ported CoreLongProvider strategy through the real
                 ValidationHarness, mark-to-market daily returns
  - blend      : src.carry.build_blended_book

Prints the summary, the year-by-year returns, and the full month-by-month
table so the monthly-consistency question can be judged directly.
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
from src.carry import BlendConfig, build_blended_book, load_funding_history, simulate_basis_carry
from src.carry.basis_carry import BasisCarryConfig  # noqa: E402
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


async def _core_leg_returns(
    symbol: str, start: str, end: str, sma: str, atr_pct: float
) -> pd.Series:
    df = await load_ohlcv(
        source="exchange",
        symbol=symbol,
        timeframe="1d",
        start=datetime.fromisoformat(start).replace(tzinfo=UTC),
        end=datetime.fromisoformat(end).replace(tzinfo=UTC),
    )
    feats = load_features_config_file(_BACKEND.parent / "config" / "features.core_long.yaml")
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
        engine_config=_engine_config(atr_pct, 1.5),
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
    eq = _mark_to_market_equity(df, list(result.events))
    ts = pd.to_datetime(df["timestamp"], utc=True)
    return pd.Series(eq, index=ts).pct_change().dropna()


def _print_month_table(monthly: pd.Series) -> None:
    by_year: dict[int, dict[int, float]] = {}
    for ts, val in monthly.items():
        by_year.setdefault(ts.year, {})[ts.month] = val * 100
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    print(f"\n{'year':<6}" + "".join(f"{m:>7}" for m in months) + f"{'YEAR':>9}", flush=True)
    for year in sorted(by_year):
        row = by_year[year]
        cells = "".join(f"{row[m]:>7.1f}" if m in row else f"{'-':>7}" for m in range(1, 13))
        year_ret = (np.prod([1 + row[m] / 100 for m in row]) - 1) * 100
        print(f"{year:<6}{cells}{year_ret:>9.1f}", flush=True)


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Carry+core blended-book backtest")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument("--carry-weight", type=float, default=0.7)
    parser.add_argument("--target-vol", type=float, default=0.13)
    parser.add_argument("--sma", default="sma_150")
    parser.add_argument("--vol-target-atr-pct", type=float, default=2.5)
    parser.add_argument("--entry-gate", action="store_true", help="carry sits out funding<0")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)

    carry_cfg = BasisCarryConfig(min_trailing_funding_8h=0.0 if args.entry_gate else -1.0)
    carry_legs = []
    for symbol in ("BTC/USDT", "ETH/USDT"):
        funding = load_funding_history(symbol, start, end)
        carry_legs.append(simulate_basis_carry(funding, carry_cfg).daily_returns)
    carry = pd.concat(carry_legs, axis=1).mean(axis=1)

    core_legs = []
    for symbol in ("BTC/USDT", "ETH/USDT"):
        core_legs.append(
            await _core_leg_returns(symbol, args.start, args.end, args.sma, args.vol_target_atr_pct)
        )
    core = pd.concat(core_legs, axis=1).mean(axis=1)

    print(f"\ncarry book: {len(carry)}d  core book: {len(core)}d", flush=True)

    configs = {
        f"{int(args.carry_weight * 100)}/{int((1 - args.carry_weight) * 100)} @ "
        f"{int(args.target_vol * 100)}% vol": BlendConfig(
            carry_weight=args.carry_weight,
            core_weight=1 - args.carry_weight,
            target_annual_vol=args.target_vol,
        ),
        "pure carry": BlendConfig(carry_weight=1.0, core_weight=0.0, target_annual_vol=None),
        "70/30 no overlay": BlendConfig(carry_weight=0.7, core_weight=0.3, target_annual_vol=None),
        "90/10 @ 8% vol": BlendConfig(carry_weight=0.9, core_weight=0.1, target_annual_vol=0.08),
    }
    print(
        f"\n{'config':<24} {'CAGR%':>7} {'vol%':>6} {'Sharpe':>7} {'maxDD%':>7} "
        f"{'+mo%':>6} {'mo.med%':>8} {'worst mo':>10}",
        flush=True,
    )
    primary = None
    for name, cfg in configs.items():
        res = build_blended_book(carry, core, cfg)
        s = res.summary()
        if primary is None:
            primary = res
        print(
            f"{name:<24} {s['cagr_pct']:>7} {s['annual_vol_pct']:>6} {s['sharpe']:>7} "
            f"{s['max_drawdown_pct']:>7} {s['pct_months_positive']:>6} "
            f"{s['median_month_pct']:>8} {s['worst_month_pct']:>6}% {s['worst_month_date']:>9}",
            flush=True,
        )

    print("\n=== primary config month-by-month return % ===", flush=True)
    _print_month_table(primary.monthly_returns)
    monthly = primary.monthly_returns
    neg = monthly[monthly < 0]
    worst = ", ".join(f"{d.strftime('%Y-%m')}: {v * 100:.1f}%" for d, v in neg.nsmallest(5).items())
    print(
        f"\nnegative months: {len(neg)}/{len(monthly)} "
        f"({len(neg) / len(monthly) * 100:.0f}%).  worst 5: {worst}",
        flush=True,
    )

    # ---- stress: funding compression, tighter leverage cap, 2022-only ----
    print("\n=== stress on the primary config ===", flush=True)
    base_cfg = next(iter(configs.values()))
    scenarios = {
        "baseline": (carry, base_cfg),
        "funding halved": (carry * 0.5, base_cfg),
        "funding -70%": (carry * 0.3, base_cfg),
        "leverage cap 1.5x": (
            carry,
            BlendConfig(
                base_cfg.carry_weight,
                base_cfg.core_weight,
                base_cfg.target_annual_vol,
                base_cfg.vol_window,
                1.5,
            ),
        ),
        "no vol overlay": (
            carry,
            BlendConfig(base_cfg.carry_weight, base_cfg.core_weight, None),
        ),
    }
    for name, (c, cfg) in scenarios.items():
        s = build_blended_book(c, core, cfg).summary()
        print(
            f"  {name:<20} CAGR {s['cagr_pct']:>5}%  Sharpe {s['sharpe']:>4}  "
            f"maxDD {s['max_drawdown_pct']:>5}%  +mo {s['pct_months_positive']:>4}%  "
            f"worst mo {s['worst_month_pct']:>5}%",
            flush=True,
        )

    # worst rolling 3-month stretch on the primary book
    roll3 = primary.equity_curve.resample("ME").last().pct_change(3).dropna()
    print(
        f"\n  worst rolling 3-month: {roll3.min() * 100:.1f}% "
        f"({roll3.idxmin().strftime('%Y-%m')}); "
        f"share of 3-month windows negative: {(roll3 < 0).mean() * 100:.0f}%",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
