from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.event import EventEnvelope, EventFamily
from src.db.repositories.event_log import fetch_events_by_correlation
from src.events.envelopes import (
    DecisionEventType,
    ExecutionEventType,
    MarketEventType,
)
from src.replay.timeline import build_timeline


@dataclass(frozen=True)
class ReplayResult:
    correlation_id: str
    events: tuple[EventEnvelope, ...]
    timeline: list[dict]
    families_present: set[EventFamily]


class ReplayEngine:
    def __init__(self, events: list[EventEnvelope]) -> None:
        self._events = events

    @classmethod
    async def from_db(cls, session: AsyncSession, correlation_id: str) -> ReplayEngine:
        events = await fetch_events_by_correlation(session, correlation_id)
        return cls(events)

    def replay_cycle(self, correlation_id: str) -> ReplayResult:
        cycle_events = sorted(
            [e for e in self._events if e.correlation_id == correlation_id],
            key=lambda e: (e.event_time, e.processing_time),
        )
        timeline = build_timeline(cycle_events)
        families = {e.event_family for e in cycle_events}
        return ReplayResult(
            correlation_id=correlation_id,
            events=tuple(cycle_events),
            timeline=timeline,
            families_present=families,
        )

    def has_full_chain(self, correlation_id: str) -> bool:
        result = self.replay_cycle(correlation_id)
        types = {e.event_type for e in result.events}
        has_market = MarketEventType.CANDLE_RECEIVED in types
        has_decision = DecisionEventType.DECISION_MADE in types
        has_execution = ExecutionEventType.ORDER_INTENT_CREATED in types or not any(
            e.event_type == DecisionEventType.DECISION_APPROVED for e in result.events
        )
        if any(e.event_type == DecisionEventType.DECISION_APPROVED for e in result.events):
            return has_market and has_decision and ExecutionEventType.ORDER_INTENT_CREATED in types
        return has_market and has_decision and has_execution
