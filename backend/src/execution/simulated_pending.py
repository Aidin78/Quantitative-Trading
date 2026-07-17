from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from src.core.contracts.execution import Order, OrderIntent
from src.core.contracts.state import StateSnapshot
from src.execution.engine import ExecutionResult
from src.execution.simulated_events import filter_events
from src.execution.simulated_positions import open_position
from src.state.transitions import StateTransitionEvent

if TYPE_CHECKING:
    from src.execution.simulated import SimulatedExecutionEngine


@dataclass(frozen=True)
class PendingEntry:
    order: Order
    intent: OrderIntent
    quantity: float
    side: Literal["BUY", "SELL"]
    position_side: Literal["LONG", "SHORT"]
    symbol: str
    stop_loss: float
    take_profit: float
    decision_event_time: datetime
    portfolio_id: str


async def process_pending_entries(
    engine: SimulatedExecutionEngine,
    bar: dict[str, Any],
    snapshot: StateSnapshot,
    *,
    symbol: str,
    timeframe: str,
    correlation_id: str,
    event_time: datetime,
    processing_time: datetime,
) -> ExecutionResult:
    events: list = []
    transitions: list[StateTransitionEvent] = []
    remaining: list[PendingEntry] = []

    for pending in engine._pending_entries:
        if pending.symbol != symbol:
            remaining.append(pending)
            continue

        fill_events, transition = open_position(
            engine,
            order=pending.order,
            quantity=pending.quantity,
            side=pending.side,
            position_side=pending.position_side,
            symbol=pending.symbol,
            stop_loss=pending.stop_loss,
            take_profit=pending.take_profit,
            bar=bar,
            snapshot=snapshot,
            correlation_id=correlation_id,
            timeframe=timeframe,
            event_time=event_time,
            processing_time=processing_time,
            causation_id=None,
            use_next_open=True,
        )
        events.extend(fill_events)
        if transition:
            transitions.append(transition)

    engine._pending_entries = remaining
    return ExecutionResult(events=filter_events(engine, events), transitions=tuple(transitions))
