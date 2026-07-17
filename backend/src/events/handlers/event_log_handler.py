from __future__ import annotations

from src.core.contracts.event import EventEnvelope, EventFamily


class EventLogHandler:
    """In-memory event log — DB persistence in Phase 4."""

    event_types: set[str] = set()

    def __init__(self, *, families: set[EventFamily] | None = None) -> None:
        self._log: list[EventEnvelope] = []
        self._families = families

    @property
    def events(self) -> list[EventEnvelope]:
        return list(self._log)

    async def handle(self, event: EventEnvelope) -> None:
        if self._families is not None and event.event_family not in self._families:
            return
        self._log.append(event)

    def clear(self) -> None:
        self._log.clear()
