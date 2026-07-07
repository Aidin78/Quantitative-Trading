from __future__ import annotations

import logging

from src.core.contracts.event import EventBus, EventHandler
from src.core.settings import get_settings
from src.events.in_memory_bus import InMemoryEventBus
from src.events.redis_bus import RedisEventBus

logger = logging.getLogger(__name__)


async def create_event_bus(
    handlers: list[EventHandler],
    *,
    redis_url: str | None = None,
    prefer_redis: bool = True,
) -> EventBus:
    """Create RedisEventBus when Redis is reachable, otherwise InMemoryEventBus."""
    if not prefer_redis:
        return InMemoryEventBus(handlers=handlers)

    settings = get_settings()
    url = redis_url or settings.redis_url
    redis_bus = RedisEventBus(url, handlers=handlers)
    if await redis_bus.connect():
        logger.info("Using RedisEventBus at %s", url)
        return redis_bus

    logger.info("Falling back to InMemoryEventBus")
    return InMemoryEventBus(handlers=handlers)
