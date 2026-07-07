from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.core.contracts.decision import Decision
from src.core.contracts.event import EventEnvelope
from src.core.contracts.state import StateSnapshot
from src.state.transitions import StateTransitionEvent


@dataclass(frozen=True)
class ExecutionResult:
    events: tuple[EventEnvelope, ...]
    transitions: tuple[StateTransitionEvent, ...] = ()


class ExecutionEngine(Protocol):
    async def execute(
        self,
        decision: Decision,
        snapshot: StateSnapshot,
        bar: dict[str, Any],
        *,
        symbol: str,
        timeframe: str,
        correlation_id: str,
        processing_time,
    ) -> ExecutionResult: ...

    async def evaluate_bar(
        self,
        bar: dict[str, Any],
        snapshot: StateSnapshot,
        *,
        symbol: str,
        timeframe: str,
        correlation_id: str,
        event_time,
        processing_time,
    ) -> ExecutionResult: ...
