from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import Base
from src.governance.hypothesis_store import (
    create_hypothesis,
    get_hypothesis,
    link_hypothesis_to_experiment,
    list_hypotheses,
    resolve_hypothesis,
    search_similar_hypotheses,
)


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
async def test_create_and_get_hypothesis(db_session: AsyncSession) -> None:
    hypothesis = await create_hypothesis(
        db_session,
        observation="Momentum performs poorly during high volatility.",
        statement="High volatility reduces the reliability of momentum signals.",
        expected_effect="Improve risk-adjusted return and reduce drawdown.",
        proposed_change="Disable momentum signals when volatility percentile exceeds 80.",
        source_experiment_run_id="erun_source001",
    )
    await db_session.commit()

    fetched = await get_hypothesis(db_session, hypothesis.hypothesis_id)
    assert fetched is not None
    assert fetched.status == "open"
    assert fetched.source_experiment_run_id == "erun_source001"
    assert fetched.tested_by_experiment_id is None


@pytest.mark.asyncio
async def test_get_hypothesis_not_found(db_session: AsyncSession) -> None:
    assert await get_hypothesis(db_session, "hyp_missing0000") is None


@pytest.mark.asyncio
async def test_list_hypotheses_filters_by_status(db_session: AsyncSession) -> None:
    a = await create_hypothesis(
        db_session,
        observation="obs a",
        statement="stmt a",
        expected_effect="effect a",
        proposed_change="change a",
    )
    b = await create_hypothesis(
        db_session,
        observation="obs b",
        statement="stmt b",
        expected_effect="effect b",
        proposed_change="change b",
    )
    await resolve_hypothesis(db_session, b.hypothesis_id, confirmed=True)
    await db_session.commit()

    open_only = await list_hypotheses(db_session, status="open")
    assert [h.hypothesis_id for h in open_only] == [a.hypothesis_id]

    confirmed_only = await list_hypotheses(db_session, status="confirmed")
    assert [h.hypothesis_id for h in confirmed_only] == [b.hypothesis_id]


@pytest.mark.asyncio
async def test_link_hypothesis_to_experiment_marks_tested(db_session: AsyncSession) -> None:
    hypothesis = await create_hypothesis(
        db_session,
        observation="obs",
        statement="stmt",
        expected_effect="effect",
        proposed_change="change",
    )
    await db_session.commit()

    linked = await link_hypothesis_to_experiment(
        db_session, hypothesis.hypothesis_id, experiment_id="exp_test001"
    )
    await db_session.commit()

    assert linked is not None
    assert linked.tested_by_experiment_id == "exp_test001"
    assert linked.status == "tested"


@pytest.mark.asyncio
async def test_link_hypothesis_not_found(db_session: AsyncSession) -> None:
    result = await link_hypothesis_to_experiment(
        db_session, "hyp_missing0000", experiment_id="exp_test001"
    )
    assert result is None


@pytest.mark.asyncio
async def test_resolve_hypothesis_confirmed_and_refuted(db_session: AsyncSession) -> None:
    confirmed = await create_hypothesis(
        db_session, observation="o", statement="s", expected_effect="e", proposed_change="c"
    )
    refuted = await create_hypothesis(
        db_session, observation="o", statement="s", expected_effect="e", proposed_change="c"
    )
    await db_session.commit()

    await resolve_hypothesis(db_session, confirmed.hypothesis_id, confirmed=True)
    await resolve_hypothesis(db_session, refuted.hypothesis_id, confirmed=False)
    await db_session.commit()

    assert (await get_hypothesis(db_session, confirmed.hypothesis_id)).status == "confirmed"
    assert (await get_hypothesis(db_session, refuted.hypothesis_id)).status == "refuted"


@pytest.mark.asyncio
async def test_search_similar_hypotheses_finds_overlapping_proposed_change(
    db_session: AsyncSession,
) -> None:
    await create_hypothesis(
        db_session,
        observation="o1",
        statement="s1",
        expected_effect="e1",
        proposed_change="Disable momentum signals when volatility percentile exceeds 80",
    )
    await create_hypothesis(
        db_session,
        observation="o2",
        statement="s2",
        expected_effect="e2",
        proposed_change="Require higher-timeframe trend confirmation before entry",
    )
    await db_session.commit()

    results = await search_similar_hypotheses(
        db_session,
        "Reduce momentum exposure when volatility percentile is high",
        min_overlap=0.2,
    )
    assert len(results) == 1
    assert "momentum" in results[0].proposed_change.lower()


@pytest.mark.asyncio
async def test_search_similar_hypotheses_empty_query_returns_nothing(
    db_session: AsyncSession,
) -> None:
    await create_hypothesis(
        db_session, observation="o", statement="s", expected_effect="e", proposed_change="ab cd"
    )
    await db_session.commit()

    results = await search_similar_hypotheses(db_session, "")
    assert results == []


@pytest.mark.asyncio
async def test_search_similar_hypotheses_no_match_below_threshold(
    db_session: AsyncSession,
) -> None:
    await create_hypothesis(
        db_session,
        observation="o",
        statement="s",
        expected_effect="e",
        proposed_change="Require higher-timeframe trend confirmation before entry",
    )
    await db_session.commit()

    results = await search_similar_hypotheses(
        db_session, "Increase minimum confidence threshold", min_overlap=0.5
    )
    assert results == []
