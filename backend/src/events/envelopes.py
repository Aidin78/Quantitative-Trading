from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from src.core.contracts.event import EventEnvelope, EventFamily


class MarketEventType:
    CANDLE_RECEIVED = "CandleReceived"
    FEATURE_SET_BUILT = "FeatureSetBuilt"
    MARKET_CONTEXT_DERIVED = "MarketContextDerived"


class SignalEventType:
    PROVIDER_OPINION = "ProviderOpinion"
    PROVIDER_SKIPPED = "ProviderSkipped"


class DecisionEventType:
    DECISION_MADE = "DecisionMade"
    DECISION_APPROVED = "DecisionApproved"
    DECISION_REJECTED = "DecisionRejected"


class ExecutionEventType:
    ORDER_INTENT_CREATED = "OrderIntentCreated"
    ORDER_SUBMITTED = "OrderSubmitted"
    ORDER_ACKNOWLEDGED = "OrderAcknowledged"
    FILL_RECEIVED = "FillReceived"
    POSITION_OPENED = "PositionOpened"
    POSITION_CLOSED = "PositionClosed"
    SIGNAL_PUBLISHED = "SignalPublished"
    ORDER_REJECTED = "OrderRejected"
    EXECUTION_FAILED = "ExecutionFailed"


def build_envelope(
    *,
    event_family: EventFamily,
    event_type: str,
    event_time: datetime,
    processing_time: datetime,
    correlation_id: str,
    symbol: str,
    timeframe: str,
    mode: Literal["validation", "live", "paper", "replay"],
    payload: dict[str, Any],
    causation_id: str | None = None,
    experiment_id: str | None = None,
    revision_id: str | None = None,
    event_id: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id or f"evt_{uuid.uuid4().hex[:12]}",
        event_family=event_family,
        event_type=event_type,
        event_time=event_time,
        processing_time=processing_time,
        correlation_id=correlation_id,
        causation_id=causation_id,
        cycle_id=correlation_id,
        symbol=symbol,
        timeframe=timeframe,
        mode=mode,
        experiment_id=experiment_id,
        revision_id=revision_id,
        payload=payload,
    )
