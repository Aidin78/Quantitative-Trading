from __future__ import annotations

from tests.mocks.fixtures import make_context, make_snapshot, make_snapshot_with_open_positions
from tests.mocks.mock_signals import consensus_buy_signals


def test_max_open_positions_rejected(engine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot_with_open_positions(3),
        correlation_id="cycle_max_positions",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_reason == "max_open_positions"


def test_max_exposure_rejected(engine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(exposure_pct=60.0),
        correlation_id="cycle_max_exposure",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_reason == "max_exposure"


def test_max_consecutive_losses_rejected(engine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(consecutive_losses=5, max_consecutive_losses=5),
        correlation_id="cycle_max_consecutive_losses",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert not decision.is_approved
    assert decision.result.rejection_reason == "max_consecutive_losses"


def test_below_max_consecutive_losses_not_rejected_on_this_check(engine, times: dict) -> None:
    decision = engine.process(
        consensus_buy_signals(times["event_time"]),
        make_context(),
        make_snapshot(consecutive_losses=4, max_consecutive_losses=5),
        correlation_id="cycle_below_max_consecutive_losses",
        event_time=times["event_time"],
        decision_time=times["decision_time"],
    )
    assert decision.result.rejection_reason != "max_consecutive_losses"
