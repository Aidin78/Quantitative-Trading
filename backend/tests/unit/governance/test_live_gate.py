from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.settings import get_settings
from src.db.base import Base
from src.db.models import BacktestRunRow
from src.governance.candidate_store import (
    create_candidate,
    promote_candidate,
    run_candidate_evaluation,
)
from src.governance.experiment_store import create_experiment, has_successful_validation
from src.governance.live_gate import LiveGovernanceGate
from src.governance.revision_store import compute_config_revision, save_revision
from src.validation.optimization_scoring import OptimizationResult, TrialResult


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


def _passing_result() -> OptimizationResult:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return OptimizationResult(
        sweep_id="sweep_test",
        symbol="BTC/USDT",
        timeframe="1h",
        train_start=now,
        train_end=now,
        test_start=now,
        test_end=now,
        holdout_valid=True,
        holdout_outcome={
            "total_trades": 40,
            "regime_analysis": {
                "by_regime": {"UP_HIGH": {"trades": 20}, "DOWN_LOW": {"trades": 20}}
            },
        },
        best=TrialResult(
            trial_id="trial_1",
            params={},
            train_score=1.0,
            train_outcome={},
            fold_scores=[1.0, 1.1, 0.9],
            fold_std=0.5,
        ),
    )


async def _seed_validated_revision(session: AsyncSession, *, label: str) -> str:
    revision = compute_config_revision(label=label)
    await save_revision(session, revision)
    session.add(
        BacktestRunRow(
            run_id=f"run_{label}",
            symbol="BTC/USDT",
            timeframe="1h",
            config={"revision_id": revision.revision_id},
            metrics={"outcome": {"total_trades": 100}},
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
    )
    return revision.revision_id


@pytest.mark.asyncio
async def test_champion_flag_off_does_not_change_behavior(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRE_CHAMPION_CANDIDATE", "false")
    try:
        revision_id = await _seed_validated_revision(db_session, label="flag-off")
        await db_session.commit()

        gate = LiveGovernanceGate()
        assert await gate.allow_start(db_session, revision_id) is True
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_champion_flag_on_allows_revision_without_candidate_lineage(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRE_CHAMPION_CANDIDATE", "true")
    try:
        revision_id = await _seed_validated_revision(db_session, label="no-lineage")
        await db_session.commit()

        gate = LiveGovernanceGate()
        assert await gate.allow_start(db_session, revision_id) is True
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_champion_flag_on_blocks_revision_with_non_champion_candidate(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRE_CHAMPION_CANDIDATE", "true")
    try:
        revision_id = await _seed_validated_revision(db_session, label="pending-champion")
        experiment = await create_experiment(db_session, revision_id=revision_id, name="exp")
        await create_candidate(db_session, experiment_id=experiment.experiment_id)
        await db_session.commit()

        gate = LiveGovernanceGate()
        assert await gate.allow_start(db_session, revision_id) is False
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_champion_flag_on_allows_revision_with_champion_candidate(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRE_CHAMPION_CANDIDATE", "true")
    try:
        revision_id = await _seed_validated_revision(db_session, label="has-champion")
        experiment = await create_experiment(db_session, revision_id=revision_id, name="exp")
        candidate = await create_candidate(db_session, experiment_id=experiment.experiment_id)
        await db_session.commit()
        await run_candidate_evaluation(db_session, candidate.candidate_id, _passing_result())
        await db_session.commit()
        await promote_candidate(db_session, candidate.candidate_id, to_state="challenger")
        await db_session.commit()
        await promote_candidate(db_session, candidate.candidate_id, to_state="champion")
        await db_session.commit()

        gate = LiveGovernanceGate()
        assert await gate.allow_start(db_session, revision_id) is True
    finally:
        get_settings.cache_clear()
