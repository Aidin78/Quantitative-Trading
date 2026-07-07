from __future__ import annotations

from src.core.contracts.event import EventEnvelope, EventFamily


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
            }
        )
    return timeline
