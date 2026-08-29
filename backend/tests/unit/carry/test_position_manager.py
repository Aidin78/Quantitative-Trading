from __future__ import annotations

import pytest

from src.carry.position_manager import (
    CarryManagerConfig,
    CarryPositionManager,
    CarryPositionState,
    CarryTarget,
)


@pytest.fixture
def mgr() -> CarryPositionManager:
    return CarryPositionManager(
        CarryManagerConfig(
            capital_multiplier=1.5,
            min_trailing_funding_8h=0.0,
            rebalance_band=0.02,
            resize_band=0.05,
        )
    )


def test_decide_target_holds_when_funding_positive(mgr: CarryPositionManager) -> None:
    t = mgr.decide_target(trailing_funding_8h=0.0001, equity=15_000.0)
    assert t.hold
    assert t.target_notional == pytest.approx(10_000.0)  # 15k / 1.5


def test_decide_target_flat_when_funding_below_threshold(mgr: CarryPositionManager) -> None:
    t = mgr.decide_target(trailing_funding_8h=-0.0002, equity=15_000.0)
    assert not t.hold
    assert t.target_notional == 0.0


def test_plan_opens_pair_from_flat(mgr: CarryPositionManager) -> None:
    plan = mgr.plan(
        CarryPositionState(),
        CarryTarget(hold=True, target_notional=10_000.0),
        spot_px=100.0,
        perp_px=100.0,
    )
    assert plan.reason == "open"
    assert plan.spot_delta_qty == pytest.approx(100.0)
    assert plan.perp_delta_qty == pytest.approx(100.0)


def test_plan_closes_pair_when_target_flat(mgr: CarryPositionManager) -> None:
    state = CarryPositionState(
        spot_qty=100.0, perp_qty=100.0, spot_entry_px=100.0, perp_entry_px=100.0
    )
    plan = mgr.plan(
        state, CarryTarget(hold=False, target_notional=0.0), spot_px=100.0, perp_px=100.0
    )
    assert plan.reason == "close"
    assert plan.spot_delta_qty == pytest.approx(-100.0)
    assert plan.perp_delta_qty == pytest.approx(-100.0)


def test_plan_noop_when_delta_flat_and_size_on_target(mgr: CarryPositionManager) -> None:
    state = CarryPositionState(
        spot_qty=100.0, perp_qty=100.0, spot_entry_px=100.0, perp_entry_px=100.0
    )
    plan = mgr.plan(
        state, CarryTarget(hold=True, target_notional=10_000.0), spot_px=100.0, perp_px=100.0
    )
    assert plan.is_noop


def test_plan_rebalances_hedge_when_delta_drifts(mgr: CarryPositionManager) -> None:
    # spot rallied to 110, perp still 100 -> net delta = 100*110 - 100*100 = +1000 on 11000 = 9%
    state = CarryPositionState(
        spot_qty=100.0, perp_qty=100.0, spot_entry_px=100.0, perp_entry_px=100.0
    )
    plan = mgr.plan(
        state, CarryTarget(hold=True, target_notional=11_000.0), spot_px=110.0, perp_px=100.0
    )
    assert plan.reason == "rebalance"
    assert plan.spot_delta_qty == 0.0
    # want perp short ~ 100*110/100 = 110 units => add 10
    assert plan.perp_delta_qty == pytest.approx(10.0, rel=1e-6)


def test_plan_resizes_when_equity_grows(mgr: CarryPositionManager) -> None:
    state = CarryPositionState(
        spot_qty=100.0, perp_qty=100.0, spot_entry_px=100.0, perp_entry_px=100.0
    )
    plan = mgr.plan(
        state, CarryTarget(hold=True, target_notional=13_000.0), spot_px=100.0, perp_px=100.0
    )
    assert plan.reason == "resize"
    assert plan.spot_delta_qty == pytest.approx(30.0)
    assert plan.perp_delta_qty == pytest.approx(30.0)


def test_apply_fill_opens_and_sets_entry(mgr: CarryPositionManager) -> None:
    s, cash_flow = mgr.apply_fill(
        CarryPositionState(),
        spot_fill_qty=100.0,
        spot_fill_px=100.0,
        perp_fill_qty=100.0,
        perp_fill_px=100.1,
        fee=5.0,
    )
    assert s.spot_qty == 100.0
    assert s.perp_qty == 100.0
    assert s.spot_entry_px == 100.0
    assert s.perp_entry_px == 100.1
    # bought 100 spot @ 100 (-10000) plus 5 fee; perp short posts margin, not cash
    assert cash_flow == pytest.approx(-10_005.0)
    assert s.flips == 1


def test_apply_fill_close_is_cash_neutral_when_delta_flat(mgr: CarryPositionManager) -> None:
    state = CarryPositionState(
        spot_qty=100.0, perp_qty=100.0, spot_entry_px=100.0, perp_entry_px=100.0
    )
    # close at 108 both legs: spot sale +10800, perp short realised 100*(100-108) = -800
    s, cash_flow = mgr.apply_fill(
        state,
        spot_fill_qty=-100.0,
        spot_fill_px=108.0,
        perp_fill_qty=-100.0,
        perp_fill_px=108.0,
    )
    assert s.spot_qty == 0.0
    assert s.perp_qty == 0.0
    assert cash_flow == pytest.approx(10_000.0)  # 10800 - 800, back to the entry notional
    assert s.flips == 1


def test_accrue_funding_credits_short_leg(mgr: CarryPositionManager) -> None:
    state = CarryPositionState(
        spot_qty=100.0, perp_qty=100.0, spot_entry_px=100.0, perp_entry_px=100.0
    )
    s = mgr.accrue_funding(state, funding_rate=0.0001, perp_px=100.0)
    assert s.accrued_funding == pytest.approx(0.0001 * 100.0 * 100.0)  # 1.0


def test_equity_marks_perp_short_to_market(mgr: CarryPositionManager) -> None:
    state = CarryPositionState(
        spot_qty=100.0,
        perp_qty=100.0,
        spot_entry_px=100.0,
        perp_entry_px=100.0,
        accrued_funding=12.0,
    )
    # price -20%: spot 8000, perp short gains +2000, net flat, plus accrued
    eq = mgr.equity(state, cash=0.0, spot_px=80.0, perp_px=80.0)
    assert eq == pytest.approx(8000.0 + 2000.0 + 12.0)
