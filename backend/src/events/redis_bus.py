from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis

from src.core.contracts.event import EventEnvelope, EventHandler

logger = logging.getLogger(__name__)

REDIS_CHANNEL = "qtp:events"


class RedisEventBus:
    """Redis Pub/Sub event bus with local handler dispatch."""

    def __init__(self, redis_url: str, handlers: list[EventHandler] | None = None) -> None:
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None
        self._handlers = list(handlers or [])
        self._published: list[EventEnvelope] = []

    @property
    def published(self) -> list[EventEnvelope]:
        return list(self._published)

    def add_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def connect(self) -> bool:
        try:
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            await self._redis.ping()
            return True
        except Exception as exc:
            logger.warning("Redis unavailable (%s), use InMemoryEventBus fallback", exc)
            if self._redis is not None:
                await self._redis.aclose()
                self._redis = None
            return False

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def publish(self, event: EventEnvelope) -> None:
        self._published.append(event)
        if self._redis is not None:
            payload = json.dumps(event.model_dump(mode="json"))
            await self._redis.publish(REDIS_CHANNEL, payload)
        await self._dispatch(event)

    async def publish_many(self, events: list[EventEnvelope]) -> None:
        for event in events:
            await self.publish(event)

    async def _dispatch(self, event: EventEnvelope) -> None:
        for handler in self._handlers:
            if not handler.event_types or event.event_type in handler.event_types:
                await handler.handle(event)

    def clear(self) -> None:
        self._published.clear()
