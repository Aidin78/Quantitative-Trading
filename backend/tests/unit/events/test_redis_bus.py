from __future__ import annotations

import pytest

from src.core.settings import get_settings
from src.events.bus_factory import create_event_bus
from src.events.handlers.logging_handler import LoggingEventHandler
from src.events.in_memory_bus import InMemoryEventBus
from src.events.redis_bus import RedisEventBus


@pytest.mark.asyncio
async def test_create_event_bus_fallback_without_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://invalid:59999/0")
    get_settings.cache_clear()
    bus = await create_event_bus([LoggingEventHandler()], prefer_redis=True)
    assert isinstance(bus, InMemoryEventBus)


@pytest.mark.asyncio
async def test_redis_event_bus_publish_dispatch() -> None:
    try:
        import fakeredis.aioredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    received: list[str] = []

    class CaptureHandler:
        event_types: set[str] = set()

        async def handle(self, event) -> None:
            received.append(event.event_type)

    bus = RedisEventBus("redis://localhost:6379/0", handlers=[CaptureHandler()])
    bus._redis = redis  # noqa: SLF001
    from datetime import UTC, datetime

    from src.core.contracts.event import EventEnvelope, EventFamily
    from src.events.envelopes import MarketEventType

    event = EventEnvelope(
        event_id="evt_test",
        event_family=EventFamily.MARKET,
        event_type=MarketEventType.CANDLE_RECEIVED,
        event_time=datetime.now(UTC),
        processing_time=datetime.now(UTC),
        correlation_id="cycle_test",
        cycle_id="cycle_test",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="paper",
        payload={},
    )
    await bus.publish(event)
    assert received == [MarketEventType.CANDLE_RECEIVED]
    await redis.aclose()
