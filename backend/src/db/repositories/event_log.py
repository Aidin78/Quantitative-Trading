from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.event import EventEnvelope, EventFamily
from src.db.models import EventLogRow


async def fetch_events_by_correlation(
    session: AsyncSession,
    correlation_id: str,
) -> list[EventEnvelope]:
    stmt = (
        select(EventLogRow)
        .where(EventLogRow.correlation_id == correlation_id)
        .order_by(EventLogRow.event_time)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_envelope(row) for row in rows]


async def fetch_all_events(session: AsyncSession) -> list[EventEnvelope]:
    stmt = select(EventLogRow).order_by(EventLogRow.event_time)
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_envelope(row) for row in rows]


def _row_to_envelope(row: EventLogRow) -> EventEnvelope:
    return EventEnvelope(
        event_id=row.event_id,
        event_family=EventFamily(row.event_family),
        event_type=row.event_type,
        event_time=row.event_time,
        processing_time=row.processing_time,
        correlation_id=row.correlation_id,
        cycle_id=row.correlation_id,
        symbol=row.symbol,
        timeframe=row.timeframe,
        mode=row.mode,  # type: ignore[arg-type]
        payload=row.payload,
    )
