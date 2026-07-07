from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.contracts.event import EventEnvelope, EventFamily
from src.db.base import Base
from src.db.repositories.backtest import persist_event
from src.db.repositories.event_log import fetch_events_by_correlation
from src.events.envelopes import build_envelope
from src.governance.revision_store import compute_config_revision, save_revision


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _governance_event(correlation_id: str = "gov_test_1") -> EventEnvelope:
    now = datetime.now(UTC)
    return build_envelope(
        event_family=EventFamily.MARKET,
        event_type="CandleReceived",
        event_time=now,
        processing_time=now,
        correlation_id=correlation_id,
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={"close": 67000.0},
        revision_id="rev_test1234567890",
        experiment_id="exp_test123456",
        causation_id="evt_parent",
    )


@pytest.mark.asyncio
async def test_persist_event_preserves_governance_ids(db_session: AsyncSession) -> None:
    event = _governance_event()
    await persist_event(db_session, event)
    await db_session.commit()

    fetched = await fetch_events_by_correlation(db_session, event.correlation_id)
    assert len(fetched) == 1
    assert fetched[0].revision_id == "rev_test1234567890"
    assert fetched[0].experiment_id == "exp_test123456"
    assert fetched[0].causation_id == "evt_parent"


def test_compute_config_revision_is_deterministic() -> None:
    first = compute_config_revision()
    second = compute_config_revision()
    assert first.revision_id == second.revision_id
    assert first.engine_config_hash == second.engine_config_hash


@pytest.mark.asyncio
async def test_save_revision_idempotent(db_session: AsyncSession) -> None:
    revision = compute_config_revision(label="test")
    await save_revision(db_session, revision)
    await save_revision(db_session, revision)
    await db_session.commit()
    again = await save_revision(db_session, revision)
    assert again.revision_id == revision.revision_id
