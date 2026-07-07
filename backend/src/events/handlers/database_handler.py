from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.contracts.event import EventEnvelope
from src.db.repositories.backtest import persist_event
from src.db.repositories.decision import (
    persist_decision_from_event,
    persist_feature_set_from_event,
)
from src.db.repositories.order import persist_execution_event


class DatabaseEventHandler:
    """Persists events to Postgres via async SQLAlchemy."""

    event_types: set[str] = set()

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._buffer: list[EventEnvelope] = []

    @property
    def events(self) -> list[EventEnvelope]:
        return list(self._buffer)

    async def handle(self, event: EventEnvelope) -> None:
        self._buffer.append(event)
        async with self._session_factory() as session:
            await persist_event(session, event)
            await persist_feature_set_from_event(session, event)
            await persist_decision_from_event(session, event)
            await persist_execution_event(session, event)
            await session.commit()

    def clear(self) -> None:
        self._buffer.clear()
