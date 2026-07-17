from __future__ import annotations

import pytest

from src.core.contracts.event import EventFamily
from src.events.envelopes import MarketEventType, build_envelope
from src.events.handlers.event_log_handler import EventLogHandler
from src.events.in_memory_bus import InMemoryEventBus
from tests.mocks.fixtures import utc_now


@pytest.mark.asyncio
async def test_in_memory_bus_dispatches_to_handlers() -> None:
    log_handler = EventLogHandler()
    bus = InMemoryEventBus(handlers=[log_handler])
    now = utc_now()
    event = build_envelope(
        event_family=EventFamily.MARKET,
        event_type=MarketEventType.CANDLE_RECEIVED,
        event_time=now,
        processing_time=now,
        correlation_id="cycle_bus",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={},
    )
    await bus.publish(event)
    assert len(bus.published) == 1
    assert len(log_handler.events) == 1


@pytest.mark.asyncio
async def test_event_log_filters_by_family() -> None:
    log_handler = EventLogHandler(families={EventFamily.EXECUTION})
    bus = InMemoryEventBus(handlers=[log_handler])
    now = utc_now()
    market = build_envelope(
        event_family=EventFamily.MARKET,
        event_type=MarketEventType.CANDLE_RECEIVED,
        event_time=now,
        processing_time=now,
        correlation_id="cycle_filter",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={},
    )
    execution = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type="position_closed",
        event_time=now,
        processing_time=now,
        correlation_id="cycle_filter",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={"pnl": 1.0},
    )
    await bus.publish_many([market, execution])
    assert len(log_handler.events) == 1
    assert log_handler.events[0].event_family == EventFamily.EXECUTION

    bus = InMemoryEventBus()
    now = utc_now()
    events = [
        build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.CANDLE_RECEIVED,
            event_time=now,
            processing_time=now,
            correlation_id="c1",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={},
        ),
        build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.FEATURE_SET_BUILT,
            event_time=now,
            processing_time=now,
            correlation_id="c1",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={},
        ),
    ]
    await bus.publish_many(events)
    assert len(bus.published) == 2
