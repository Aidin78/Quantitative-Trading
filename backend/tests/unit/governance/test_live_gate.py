from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import Base
from src.db.models import BacktestRunRow
from src.governance.experiment_store import has_successful_validation
from src.governance.live_gate import LiveGovernanceGate


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_has_successful_validation_from_backtest_run(db_session: AsyncSession) -> None:
    db_session.add(
        BacktestRunRow(
            run_id="run_gate_test",
            symbol="BTC/USDT",
            timeframe="1h",
            config={"revision_id": "rev_gate_ok"},
            metrics={"outcome": {"total_trades": 100}},
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    assert await has_successful_validation(db_session, "rev_gate_ok") is True
    assert await has_successful_validation(db_session, "rev_missing") is False


@pytest.mark.asyncio
async def test_live_gate_allows_dev_without_revision(db_session: AsyncSession) -> None:
    gate = LiveGovernanceGate()
    assert await gate.allow_start(db_session, None) is True
