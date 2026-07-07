from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.core.contracts.event import EventEnvelope, EventFamily
from src.events.envelopes import DecisionEventType
from src.events.handlers.websocket_handler import WebSocketEventHandler


@pytest.mark.asyncio
async def test_websocket_handler_broadcasts_rejection() -> None:
    handler = WebSocketEventHandler()
    event = EventEnvelope(
        event_id="evt_1",
        event_family=EventFamily.DECISION,
        event_type=DecisionEventType.DECISION_REJECTED,
        event_time=datetime.now(UTC),
        processing_time=datetime.now(UTC),
        correlation_id="cycle_1",
        cycle_id="cycle_1",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "decision_id": "dec_1",
            "rejection_reason": "low_confidence",
            "rejection_stage": "aggregator",
        },
    )
    with patch(
        "src.events.handlers.websocket_handler.broadcast_decision",
        new_callable=AsyncMock,
    ) as broadcast:
        await handler.handle(event)
        broadcast.assert_awaited_once()
        assert broadcast.await_args.kwargs["result"] == "rejected"
