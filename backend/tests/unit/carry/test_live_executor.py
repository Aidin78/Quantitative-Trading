from __future__ import annotations

import pytest

from src.carry.live_executor import CarryExchange, LiveCarryExecutor, PartialCarryFill
from src.carry.position_manager import RebalancePlan


class _FakeClient:
    """Minimal ccxt stand-in: records orders, returns deterministic fills."""

    def __init__(self, *, last: float, fail_on: str | None = None) -> None:
        self.last = last
        self.fail_on = fail_on
        self.orders: list[tuple] = []

    def fetch_ticker(self, sym):
        return {"last": self.last}

    def create_order(self, sym, otype, side, amount, price=None, params=None):
        if self.fail_on == side:
            raise RuntimeError("exchange rejected order")
        self.orders.append((sym, side, amount, params or {}))
        return {
            "filled": amount,
            "average": self.last,
            "fees": [{"cost": amount * self.last * 0.0004}],
        }


def _exchange(spot_last=100.0, perp_last=100.0, perp_fail=None) -> CarryExchange:
    return CarryExchange(
        _FakeClient(last=spot_last),
        _FakeClient(last=perp_last, fail_on=perp_fail),
        "BTC/USDT",
    )


def test_execute_noop_returns_none() -> None:
    ex = LiveCarryExecutor(_exchange())
    assert ex.execute(RebalancePlan(0.0, 0.0, "noop"), spot_px=100.0, perp_px=100.0) is None


def test_open_places_spot_buy_and_perp_short() -> None:
    exch = _exchange()
    report = LiveCarryExecutor(exch).execute(
        RebalancePlan(spot_delta_qty=2.0, perp_delta_qty=2.0, reason="open"),
        spot_px=100.0,
        perp_px=100.0,
    )
    assert report.reason == "open"
    assert report.spot_fill_qty == pytest.approx(2.0)
    assert report.perp_fill_qty == pytest.approx(2.0)
    assert report.fee > 0
    assert exch._spot.orders[0][1] == "buy"  # noqa: SLF001
    assert exch._fut.orders[0][1] == "sell"  # noqa: SLF001


def test_close_reduces_both_legs_reduce_only_on_perp() -> None:
    exch = _exchange()
    LiveCarryExecutor(exch).execute(
        RebalancePlan(spot_delta_qty=-2.0, perp_delta_qty=-2.0, reason="close"),
        spot_px=100.0,
        perp_px=100.0,
    )
    assert exch._spot.orders[0][1] == "sell"  # noqa: SLF001
    assert exch._fut.orders[0][1] == "buy"  # noqa: SLF001
    assert exch._fut.orders[0][3].get("reduceOnly") is True  # noqa: SLF001


def test_perp_failure_after_spot_fill_unwinds_spot_and_raises() -> None:
    exch = _exchange(perp_fail="sell")  # perp short will fail
    with pytest.raises(PartialCarryFill):
        LiveCarryExecutor(exch).execute(
            RebalancePlan(spot_delta_qty=2.0, perp_delta_qty=2.0, reason="open"),
            spot_px=100.0,
            perp_px=100.0,
        )
    # spot was bought then sold back
    sides = [o[1] for o in exch._spot.orders]  # noqa: SLF001
    assert sides == ["buy", "sell"]


def test_signs_negative_delta_reports_negative_fill_qty() -> None:
    report = LiveCarryExecutor(_exchange()).execute(
        RebalancePlan(spot_delta_qty=-1.5, perp_delta_qty=-1.5, reason="resize"),
        spot_px=100.0,
        perp_px=100.0,
    )
    assert report.spot_fill_qty == pytest.approx(-1.5)
    assert report.perp_fill_qty == pytest.approx(-1.5)
