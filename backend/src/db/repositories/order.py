from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.event import EventEnvelope
from src.db.models import FillRow, OrderRow
from src.events.envelopes import ExecutionEventType


async def persist_order(session: AsyncSession, event: EventEnvelope) -> None:
    order = event.payload.get("order", {})
    session.add(
        OrderRow(
            order_id=order["order_id"],
            intent_id=order["intent_id"],
            decision_id=event.payload.get("decision_id", ""),
            correlation_id=event.correlation_id,
            status=order.get("status", "submitted"),
            venue=event.payload.get("venue", "simulator"),
            payload=event.payload,
            created_at=event.processing_time,
        )
    )


async def persist_fill(session: AsyncSession, event: EventEnvelope) -> None:
    fill = event.payload["fill"]
    session.add(
        FillRow(
            fill_id=fill["fill_id"],
            order_id=fill["order_id"],
            price=float(fill["price"]),
            quantity=float(fill["quantity"]),
            fee=float(fill["fee"]),
            slippage_bps=float(fill["slippage_bps"]),
            fill_time=datetime.fromisoformat(fill["fill_time"])
            if isinstance(fill["fill_time"], str)
            else fill["fill_time"],
            fill_model_id=event.payload.get("fill_model_id"),
            created_at=datetime.now(UTC),
        )
    )


async def persist_execution_event(session: AsyncSession, event: EventEnvelope) -> None:
    if event.event_type == ExecutionEventType.ORDER_SUBMITTED:
        await persist_order(session, event)
    elif event.event_type == ExecutionEventType.FILL_RECEIVED:
        await persist_fill(session, event)
