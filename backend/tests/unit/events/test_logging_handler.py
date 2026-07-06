from __future__ import annotations

import logging

import pytest

from src.core.contracts.event import EventFamily
from src.events.envelopes import MarketEventType, build_envelope
from src.events.handlers.logging_handler import LoggingEventHandler
from src.events.in_memory_bus import InMemoryEventBus
from tests.mocks.fixtures import utc_now


@pytest.mark.asyncio
async def test_logging_handler_receives_events(caplog: pytest.LogCaptureFixture) -> None:
    bus = InMemoryEventBus(handlers=[LoggingEventHandler()])
    now = utc_now()
    event = build_envelope(
        event_family=EventFamily.MARKET,
        event_type=MarketEventType.CANDLE_RECEIVED,
        event_time=now,
        processing_time=now,
        correlation_id="cycle_log",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={},
    )
    with caplog.at_level(logging.INFO):
        await bus.publish(event)
    assert "CandleReceived" in caplog.text
    assert "cycle_log" in caplog.text
