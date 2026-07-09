from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import Base
from src.db.models import ExperimentRunRow
from src.governance.experiment_store import (
    create_experiment,
    delete_experiment,
    delete_experiments,
    get_experiment,
    list_experiments,
)
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


async def _seed_experiment(session: AsyncSession, name: str) -> str:
    revision = compute_config_revision(label=name)
    await save_revision(session, revision)
    experiment = await create_experiment(
        session,
        revision_id=revision.revision_id,
        name=name,
    )
    return experiment.experiment_id


@pytest.mark.asyncio
async def test_delete_experiment_removes_runs(db_session: AsyncSession) -> None:
    exp_id = await _seed_experiment(db_session, "delete-me")
    revision = compute_config_revision(label="delete-me")
    db_session.add(
        ExperimentRunRow(
            run_id="erun_test00001",
            experiment_id=exp_id,
            revision_id=revision.revision_id,
            started_at=datetime.now(UTC),
            completed_at=None,
            status="completed",
            metrics_summary={"total_trades": 5},
        )
    )
    await db_session.commit()

    removed = await delete_experiment(db_session, exp_id)
    await db_session.commit()

    assert removed is True
    assert await get_experiment(db_session, exp_id) is None
    assert await db_session.get(ExperimentRunRow, "erun_test00001") is None


@pytest.mark.asyncio
async def test_delete_experiment_not_found(db_session: AsyncSession) -> None:
    removed = await delete_experiment(db_session, "exp_missing0000")
    assert removed is False


@pytest.mark.asyncio
async def test_delete_experiments_bulk(db_session: AsyncSession) -> None:
    exp_a = await _seed_experiment(db_session, "bulk-a")
    exp_b = await _seed_experiment(db_session, "bulk-b")
    await db_session.commit()

    deleted, not_found, skipped = await delete_experiments(
        db_session,
        [exp_a, exp_b, "exp_missing0000"],
        skip_ids=frozenset({exp_b}),
    )
    await db_session.commit()

    assert deleted == [exp_a]
    assert not_found == ["exp_missing0000"]
    assert skipped == [exp_b]
    assert await get_experiment(db_session, exp_a) is None
    assert await get_experiment(db_session, exp_b) is not None
    remaining = await list_experiments(db_session)
    assert len(remaining) == 1
    assert remaining[0].experiment_id == exp_b
