from __future__ import annotations

from src.core.contracts.event import EventEnvelope


class EventLogHandler:
    """In-memory event log — DB persistence in Phase 4."""

    event_types: set[str] = set()

    def __init__(self) -> None:
        self._log: list[EventEnvelope] = []

    @property
    def events(self) -> list[EventEnvelope]:
        return list(self._log)

    async def handle(self, event: EventEnvelope) -> None:
        self._log.append(event)

    def clear(self) -> None:
        self._log.clear()
