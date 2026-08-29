from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.carry.carry_runner import CarryRunner, PaperCarryExecutor
from src.carry.perp_provider import HistoricalPerpProvider, PerpSnapshot
from src.carry.position_manager import CarryManagerConfig


def _snap(day: int, px: float, funding: float, trail: float) -> PerpSnapshot:
    return PerpSnapshot(
        ts=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=day),
        symbol="BTC/USDT",
        spot_px=px,
        perp_mark_px=px,
        funding_rate=funding,
        trailing_funding_8h=trail,
        is_funding_time=True,
    )


def test_runner_opens_then_earns_funding_delta_neutral() -> None:
    runner = CarryRunner(
        PaperCarryExecutor(taker_bps=0.0, slippage_bps=0.0),
        initial_capital=15_000.0,
        config=CarryManagerConfig(capital_multiplier=1.5, min_trailing_funding_8h=0.0),
    )
    # day 0: open. days 1..30: price swings hard but funding steady positive.
    snaps = [_snap(0, 100.0, 0.0, 0.0001)]
    rng = np.random.default_rng(0)
    px = 100.0
    for d in range(1, 31):
        px *= 1 + rng.normal(0, 0.04)
        snaps.append(_snap(d, px, 0.0003, 0.0001))  # ~3bp/day funding
    runner.run(snaps)

    assert runner.log.actions[0] == "open"
    # delta-neutral: equity should be up ~ funding earned, not tracking price
    start_eq, end_eq = runner.log.equity[1], runner.log.equity[-1]
    assert end_eq > start_eq  # made money from funding
    # and it did NOT swing like the underlying (which moved a lot)
    assert abs(end_eq / start_eq - 1) < 0.05


def test_runner_closes_when_funding_turns_negative() -> None:
    runner = CarryRunner(
        PaperCarryExecutor(taker_bps=1.0, slippage_bps=1.0),
        initial_capital=15_000.0,
        config=CarryManagerConfig(min_trailing_funding_8h=0.0),
    )
    snaps = [_snap(d, 100.0, 0.0002, 0.0001) for d in range(10)]
    snaps += [_snap(d, 100.0, -0.0002, -0.0002) for d in range(10, 20)]
    runner.run(snaps)
    assert "open" in runner.log.actions
    assert "close" in runner.log.actions
    assert not runner.state.in_market


def test_historical_provider_chain_matches_backtest_direction() -> None:
    """Runner over a historical provider should make money when funding was
    net-positive over the window — same sign as simulate_basis_carry."""
    from src.carry.basis_carry import simulate_basis_carry

    idx = pd.date_range("2023-01-01", periods=200, freq="D", tz="UTC")
    rng = np.random.default_rng(1)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.03, len(idx)))
    ohlcv = pd.DataFrame({"timestamp": idx, "close": close})
    fund_ts = pd.date_range("2023-01-01", periods=len(idx) * 3, freq="8h", tz="UTC")
    funding = pd.DataFrame({"timestamp": fund_ts, "funding_rate": np.full(len(fund_ts), 0.00012)})

    provider = HistoricalPerpProvider("BTC/USDT", ohlcv, funding)
    runner = CarryRunner(
        PaperCarryExecutor(taker_bps=2.0, slippage_bps=2.0),
        initial_capital=15_000.0,
        config=CarryManagerConfig(min_trailing_funding_8h=-1.0),
    )
    runner.run(provider.snapshots())
    runner_ret = runner.log.equity[-1] / runner.log.equity[0] - 1

    bt = simulate_basis_carry(funding)
    bt_ret = (1 + bt.daily_returns).prod() - 1

    assert runner_ret > 0
    assert bt_ret > 0
    # same ballpark (both ~funding earned on 1.5x capital, minus costs)
    assert runner_ret == pytest.approx(bt_ret, abs=0.03)
