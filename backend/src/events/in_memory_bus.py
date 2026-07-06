from __future__ import annotations

from src.core.contracts.event import EventEnvelope, EventHandler


class InMemoryEventBus:
    def __init__(self, handlers: list[EventHandler] | None = None) -> None:
        self._handlers = list(handlers or [])
        self._published: list[EventEnvelope] = []

    @property
    def published(self) -> list[EventEnvelope]:
        return list(self._published)

    def add_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def publish(self, event: EventEnvelope) -> None:
        self._published.append(event)
        for handler in self._handlers:
            if not handler.event_types or event.event_type in handler.event_types:
                await handler.handle(event)

    async def publish_many(self, events: list[EventEnvelope]) -> None:
        for event in events:
            await self.publish(event)

    def clear(self) -> None:
        self._published.clear()
