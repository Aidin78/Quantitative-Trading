from __future__ import annotations

from src.core.contracts.event import EventEnvelope, EventFamily
from src.events.envelopes import (
    DecisionEventType,
    ExecutionEventType,
    MarketEventType,
    SignalEventType,
)


def _event_summary(event: EventEnvelope) -> str:
    payload = event.payload
    event_type = event.event_type

    if event_type == MarketEventType.CANDLE_RECEIVED:
        return f"Candle close {payload.get('close')}"
    if event_type == MarketEventType.FEATURE_SET_BUILT:
        return f"Features built ({payload.get('feature_version')})"
    if event_type == MarketEventType.MARKET_CONTEXT_DERIVED:
        trend = payload.get("trend", "?")
        vol = payload.get("volatility", "?")
        return f"Context: trend={trend}, vol={vol}"
    if event_type == SignalEventType.PROVIDER_OPINION:
        return (
            f"{payload.get('provider_id')}: {payload.get('side')} " f"({payload.get('confidence')})"
        )
    if event_type == SignalEventType.PROVIDER_SKIPPED:
        return f"{payload.get('provider_id')} skipped"
    if event_type == DecisionEventType.DECISION_MADE:
        return f"Decision made ({payload.get('result')})"
    if event_type == DecisionEventType.DECISION_APPROVED:
        side = payload.get("final_signal", {}).get("side", payload.get("side"))
        return f"Approved {side}"
    if event_type == DecisionEventType.DECISION_REJECTED:
        return f"Rejected: {payload.get('rejection_reason', 'unknown')}"
    if event_type == ExecutionEventType.ORDER_INTENT_CREATED:
        return f"Order intent {payload.get('side')} qty={payload.get('quantity')}"
    if event_type == ExecutionEventType.FILL_RECEIVED:
        return f"Fill {payload.get('side')} @ {payload.get('price')}"
    if event_type == ExecutionEventType.POSITION_OPENED:
        return "Position opened"
    if event_type == ExecutionEventType.POSITION_CLOSED:
        return "Position closed"
    return event_type


def build_timeline(events: list[EventEnvelope]) -> list[dict]:
    family_order = {
        EventFamily.MARKET: 0,
        EventFamily.SIGNAL: 1,
        EventFamily.DECISION: 2,
        EventFamily.EXECUTION: 3,
    }
    sorted_events = sorted(
        events,
        key=lambda e: (e.event_time, family_order.get(e.event_family, 99), e.processing_time),
    )
    timeline: list[dict] = []
    for event in sorted_events:
        timeline.append(
            {
                "event_id": event.event_id,
                "event_family": event.event_family.value,
                "event_type": event.event_type,
                "event_time": event.event_time.isoformat(),
                "processing_time": event.processing_time.isoformat(),
                "correlation_id": event.correlation_id,
                "causation_id": event.causation_id,
                "summary": _event_summary(event),
            }
        )
    return timeline
