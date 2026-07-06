from __future__ import annotations

from src.core.contracts.event import EventFamily
from src.events.envelopes import DecisionEventType, MarketEventType, build_envelope
from tests.mocks.fixtures import utc_now


def test_build_envelope_sets_cycle_id_equal_to_correlation() -> None:
    now = utc_now()
    event = build_envelope(
        event_family=EventFamily.MARKET,
        event_type=MarketEventType.FEATURE_SET_BUILT,
        event_time=now,
        processing_time=now,
        correlation_id="cycle_test",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={"feature_set_id": "fs_1"},
    )
    assert event.cycle_id == "cycle_test"
    assert event.event_type == MarketEventType.FEATURE_SET_BUILT


def test_decision_event_types_defined() -> None:
    assert DecisionEventType.DECISION_APPROVED == "DecisionApproved"
    assert DecisionEventType.DECISION_REJECTED == "DecisionRejected"


def test_execution_event_types_defined() -> None:
    from src.events.envelopes import ExecutionEventType

    assert ExecutionEventType.ORDER_INTENT_CREATED == "OrderIntentCreated"
    assert ExecutionEventType.FILL_RECEIVED == "FillReceived"
