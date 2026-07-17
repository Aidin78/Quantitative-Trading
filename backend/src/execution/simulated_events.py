from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.core.contracts.event import EventFamily
from src.events.envelopes import ExecutionEventType, build_envelope

if TYPE_CHECKING:
    from src.execution.simulated import SimulatedExecutionEngine


def filter_events(engine: SimulatedExecutionEngine, events: list) -> tuple:
    if engine._emit_events:
        return tuple(events)
    return tuple(e for e in events if e.event_type in engine._SCORE_OUTCOME_TYPES)


def execution_failed(
    engine: SimulatedExecutionEngine,
    event_time: datetime,
    processing_time: datetime,
    correlation_id: str,
    symbol: str,
    timeframe: str,
    *,
    error: str,
    stage: str,
) -> Any:
    return build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.EXECUTION_FAILED,
        event_time=event_time,
        processing_time=processing_time,
        correlation_id=correlation_id,
        symbol=symbol,
        timeframe=timeframe,
        mode=engine._mode,
        payload={"error": error, "stage": stage},
    )
