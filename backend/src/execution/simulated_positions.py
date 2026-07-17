from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from src.core.contracts.event import EventFamily
from src.core.contracts.execution import Fill, Order
from src.core.contracts.state import PositionState, StateSnapshot
from src.events.envelopes import ExecutionEventType, build_envelope
from src.execution.simulated_pricing import fill_price
from src.state.transitions import StateTransitionEvent

if TYPE_CHECKING:
    from src.execution.simulated import SimulatedExecutionEngine


def open_position(
    engine: SimulatedExecutionEngine,
    *,
    order: Order,
    quantity: float,
    side: str,
    position_side: Literal["LONG", "SHORT"],
    symbol: str,
    stop_loss: float,
    take_profit: float,
    bar: dict[str, Any],
    snapshot: StateSnapshot,
    correlation_id: str,
    timeframe: str,
    event_time: datetime,
    processing_time: datetime,
    causation_id: str | None,
    use_next_open: bool = False,
) -> tuple[list, StateTransitionEvent | None]:
    price = fill_price(engine, bar, side, use_next_open=use_next_open)
    fee = price * quantity * engine._fill_model.fee_bps / 10_000
    fill = Fill(
        fill_id=f"fill_{uuid.uuid4().hex[:12]}",
        order_id=order.order_id,
        price=price,
        quantity=quantity,
        fee=fee,
        slippage_bps=engine._fill_model.slippage_bps,
        fill_time=event_time,
    )

    events: list = []
    fill_event_id: str | None = None
    if engine._emit_events:
        fill_event = build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.FILL_RECEIVED,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=engine._mode,
            causation_id=causation_id,
            payload={
                "fill": fill.model_dump(mode="json"),
                "fill_model_id": engine._fill_model.model_id,
            },
        )
        events.append(fill_event)
        fill_event_id = fill_event.event_id

    position_id = f"pos_{uuid.uuid4().hex[:12]}"
    position = PositionState(
        position_id=position_id,
        symbol=symbol,
        side=position_side,
        quantity=quantity,
        entry_price=price,
        entry_time=event_time,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
    engine._position_bars[position_id] = 0
    engine._position_orders[position_id] = order.order_id

    open_event = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.POSITION_OPENED,
        event_time=event_time,
        processing_time=processing_time,
        correlation_id=correlation_id,
        symbol=symbol,
        timeframe=timeframe,
        mode=engine._mode,
        causation_id=fill_event_id,
        payload={
            "position_id": position_id,
            "entry_fill_id": fill.fill_id,
            "position": position.model_dump(mode="json"),
        },
    )
    events.append(open_event)

    transition = StateTransitionEvent(
        transition_id=f"trans_{uuid.uuid4().hex[:12]}",
        portfolio_id=snapshot.portfolio.portfolio_id,
        transition_type="position_opened",
        payload={
            "position": position.model_dump(mode="json"),
            "fill": fill.model_dump(mode="json"),
            "cost": price * quantity + fee,
        },
        event_time=event_time,
        correlation_id=correlation_id,
    )
    return events, transition


def close_position(
    engine: SimulatedExecutionEngine,
    *,
    position: PositionState,
    exit_price: float,
    exit_reason: str,
    snapshot: StateSnapshot,
    symbol: str,
    timeframe: str,
    correlation_id: str,
    event_time: datetime,
    processing_time: datetime,
) -> tuple[list, StateTransitionEvent]:
    fill_price_value = exit_price
    fee = fill_price_value * position.quantity * engine._fill_model.fee_bps / 10_000
    order_id = engine._position_orders.get(position.position_id, f"ord_{position.position_id}")
    fill = Fill(
        fill_id=f"fill_{uuid.uuid4().hex[:12]}",
        order_id=order_id,
        price=fill_price_value,
        quantity=position.quantity,
        fee=fee,
        slippage_bps=engine._fill_model.slippage_bps,
        fill_time=event_time,
    )

    if position.side == "LONG":
        pnl = (fill_price_value - position.entry_price) * position.quantity - fee
    else:
        pnl = (position.entry_price - fill_price_value) * position.quantity - fee

    events: list = []
    fill_event_id: str | None = None
    if engine._emit_events:
        fill_event = build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.FILL_RECEIVED,
            event_time=event_time,
            processing_time=processing_time,
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=engine._mode,
            payload={
                "fill": fill.model_dump(mode="json"),
                "fill_model_id": engine._fill_model.model_id,
                "exit": True,
            },
        )
        events.append(fill_event)
        fill_event_id = fill_event.event_id

    close_event = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.POSITION_CLOSED,
        event_time=event_time,
        processing_time=processing_time,
        correlation_id=correlation_id,
        symbol=symbol,
        timeframe=timeframe,
        mode=engine._mode,
        causation_id=fill_event_id,
        payload={
            "position_id": position.position_id,
            "exit_reason": exit_reason,
            "exit_price": fill_price_value,
            "pnl": pnl,
            "fill_id": fill.fill_id,
            "entry_price": position.entry_price,
            "side": position.side,
            "quantity": position.quantity,
            "stop_loss": position.stop_loss,
            "take_profit": position.take_profit,
            "bars_held": engine._position_bars.get(position.position_id, 0),
        },
    )
    events.append(close_event)

    transition = StateTransitionEvent(
        transition_id=f"trans_{uuid.uuid4().hex[:12]}",
        portfolio_id=snapshot.portfolio.portfolio_id,
        transition_type="position_closed",
        payload={
            "position_id": position.position_id,
            "fill": fill.model_dump(mode="json"),
            "pnl": pnl,
            "exit_reason": exit_reason,
        },
        event_time=event_time,
        correlation_id=correlation_id,
    )
    engine._position_bars.pop(position.position_id, None)
    engine._position_orders.pop(position.position_id, None)
    return events, transition
