from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import Base
from src.governance.candidate_store import (
    create_candidate,
    get_candidate,
    list_candidate_evaluations,
    list_candidates,
    promote_candidate,
    run_candidate_evaluation,
)
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


def _failing_result() -> OptimizationResult:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return OptimizationResult(
        sweep_id="sweep_fail",
        symbol="BTC/USDT",
        timeframe="1h",
        train_start=now,
        train_end=now,
        test_start=now,
        test_end=now,
        holdout_valid=False,
        holdout_outcome={"total_trades": 5, "regime_analysis": {}},
    )


@pytest.mark.asyncio
async def test_create_and_get_candidate(db_session: AsyncSession) -> None:
    candidate = await create_candidate(db_session, experiment_id="exp_1")
    await db_session.commit()

    fetched = await get_candidate(db_session, candidate.candidate_id)
    assert fetched is not None
    assert fetched.state == "candidate"
    assert fetched.experiment_id == "exp_1"


@pytest.mark.asyncio
async def test_run_candidate_evaluation_accepts_and_does_not_reject(
    db_session: AsyncSession,
) -> None:
    candidate = await create_candidate(db_session, experiment_id="exp_1")
    await db_session.commit()

    evaluation = await run_candidate_evaluation(
        db_session, candidate.candidate_id, _passing_result()
    )
    await db_session.commit()

    assert evaluation is not None
    assert evaluation.decision == "accepted"
    fetched = await get_candidate(db_session, candidate.candidate_id)
    assert fetched.state == "candidate"


@pytest.mark.asyncio
async def test_run_candidate_evaluation_rejects_and_updates_state(
    db_session: AsyncSession,
) -> None:
    candidate = await create_candidate(db_session, experiment_id="exp_1")
    await db_session.commit()

    evaluation = await run_candidate_evaluation(
        db_session, candidate.candidate_id, _failing_result()
    )
    await db_session.commit()

    assert evaluation.decision == "rejected"
    fetched = await get_candidate(db_session, candidate.candidate_id)
    assert fetched.state == "rejected"


@pytest.mark.asyncio
async def test_promote_requires_accepted_evaluation(db_session: AsyncSession) -> None:
    candidate = await create_candidate(db_session, experiment_id="exp_1")
    await db_session.commit()

    with pytest.raises(ValueError, match="accepted"):
        await promote_candidate(db_session, candidate.candidate_id, to_state="challenger")


@pytest.mark.asyncio
async def test_promote_to_challenger_then_champion(db_session: AsyncSession) -> None:
    candidate = await create_candidate(db_session, experiment_id="exp_1")
    await db_session.commit()
    await run_candidate_evaluation(db_session, candidate.candidate_id, _passing_result())
    await db_session.commit()

    challenger = await promote_candidate(db_session, candidate.candidate_id, to_state="challenger")
    await db_session.commit()
    assert challenger.state == "challenger"

    champion = await promote_candidate(db_session, candidate.candidate_id, to_state="champion")
    await db_session.commit()
    assert champion.state == "champion"


@pytest.mark.asyncio
async def test_promoting_new_champion_archives_previous_champion(
    db_session: AsyncSession,
) -> None:
    old = await create_candidate(db_session, experiment_id="exp_old")
    new = await create_candidate(db_session, experiment_id="exp_new")
    await db_session.commit()
    for cand in (old, new):
        await run_candidate_evaluation(db_session, cand.candidate_id, _passing_result())
        await db_session.commit()
        await promote_candidate(db_session, cand.candidate_id, to_state="challenger")
        await db_session.commit()

    await promote_candidate(db_session, old.candidate_id, to_state="champion")
    await db_session.commit()

    await promote_candidate(db_session, new.candidate_id, to_state="champion")
    await db_session.commit()

    old_fetched = await get_candidate(db_session, old.candidate_id)
    new_fetched = await get_candidate(db_session, new.candidate_id)
    assert old_fetched.state == "archived"
    assert new_fetched.state == "champion"


@pytest.mark.asyncio
async def test_invalid_transition_raises(db_session: AsyncSession) -> None:
    candidate = await create_candidate(db_session, experiment_id="exp_1")
    await db_session.commit()

    with pytest.raises(ValueError, match="Cannot transition"):
        await promote_candidate(db_session, candidate.candidate_id, to_state="champion")


@pytest.mark.asyncio
async def test_list_candidates_filters_by_state(db_session: AsyncSession) -> None:
    a = await create_candidate(db_session, experiment_id="exp_a")
    b = await create_candidate(db_session, experiment_id="exp_b")
    await db_session.commit()
    await run_candidate_evaluation(db_session, b.candidate_id, _failing_result())
    await db_session.commit()

    open_candidates = await list_candidates(db_session, state="candidate")
    assert [c.candidate_id for c in open_candidates] == [a.candidate_id]

    rejected = await list_candidates(db_session, state="rejected")
    assert [c.candidate_id for c in rejected] == [b.candidate_id]


@pytest.mark.asyncio
async def test_list_candidate_evaluations_most_recent_first(db_session: AsyncSession) -> None:
    candidate = await create_candidate(db_session, experiment_id="exp_1")
    await db_session.commit()
    await run_candidate_evaluation(db_session, candidate.candidate_id, _passing_result())
    await db_session.commit()

    evaluations = await list_candidate_evaluations(db_session, candidate.candidate_id)
    assert len(evaluations) == 1
    assert evaluations[0].decision == "accepted"
