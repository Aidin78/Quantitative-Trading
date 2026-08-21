from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import Base
from src.db.models import DecisionRecordRow, ExperimentRunRow
from src.governance.experiment_comparator import compare_experiments
from src.governance.experiment_store import create_experiment
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
    experiment = await create_experiment(session, revision_id=revision.revision_id, name=name)
    return experiment.experiment_id


def _decision_log(*, side: str) -> dict:
    return {
        "market_filter": {"passed": True},
        "aggregation": {"side": side, "confidence": 0.7},
        "risk_check": {"passed": True, "checks": []},
    }


@pytest.mark.asyncio
async def test_compare_experiments_computes_metrics_delta(db_session: AsyncSession) -> None:
    exp_a = await _seed_experiment(db_session, "baseline")
    exp_b = await _seed_experiment(db_session, "aggressive")

    db_session.add(
        ExperimentRunRow(
            run_id="erun_a",
            experiment_id=exp_a,
            revision_id="rev_a",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            status="completed",
            metrics_summary={"sharpe_ratio": 1.0, "max_drawdown_pct": 5.0, "win_rate": 0.5},
        )
    )
    db_session.add(
        ExperimentRunRow(
            run_id="erun_b",
            experiment_id=exp_b,
            revision_id="rev_b",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            status="completed",
            metrics_summary={"sharpe_ratio": 1.5, "max_drawdown_pct": 3.0, "win_rate": 0.6},
        )
    )
    await db_session.commit()

    comparison = await compare_experiments(db_session, exp_a, exp_b)
    assert comparison.metrics_delta == {
        "max_drawdown_pct": pytest.approx(-2.0),
        "sharpe_ratio": pytest.approx(0.5),
        "win_rate": pytest.approx(0.1),
    }
    assert comparison.a_run_count == 1
    assert comparison.b_run_count == 1


@pytest.mark.asyncio
async def test_compare_experiments_only_diffs_shared_metric_keys(db_session: AsyncSession) -> None:
    exp_a = await _seed_experiment(db_session, "a")
    exp_b = await _seed_experiment(db_session, "b")

    db_session.add(
        ExperimentRunRow(
            run_id="erun_a2",
            experiment_id=exp_a,
            revision_id="rev_a",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            status="completed",
            metrics_summary={"sharpe_ratio": 1.0, "unique_to_a": 9.0},
        )
    )
    db_session.add(
        ExperimentRunRow(
            run_id="erun_b2",
            experiment_id=exp_b,
            revision_id="rev_b",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            status="completed",
            metrics_summary={"sharpe_ratio": 2.0, "unique_to_b": 4.0},
        )
    )
    await db_session.commit()

    comparison = await compare_experiments(db_session, exp_a, exp_b)
    assert comparison.metrics_delta == {"sharpe_ratio": pytest.approx(1.0)}


@pytest.mark.asyncio
async def test_compare_experiments_ignores_incomplete_runs(db_session: AsyncSession) -> None:
    exp_a = await _seed_experiment(db_session, "a")
    exp_b = await _seed_experiment(db_session, "b")

    db_session.add(
        ExperimentRunRow(
            run_id="erun_a3",
            experiment_id=exp_a,
            revision_id="rev_a",
            started_at=datetime.now(UTC),
            completed_at=None,
            status="running",
            metrics_summary=None,
        )
    )
    await db_session.commit()

    comparison = await compare_experiments(db_session, exp_a, exp_b)
    assert comparison.metrics_delta == {}


@pytest.mark.asyncio
async def test_compare_experiments_counts_decision_diffs_by_timestamp(
    db_session: AsyncSession,
) -> None:
    exp_a = await _seed_experiment(db_session, "a")
    exp_b = await _seed_experiment(db_session, "b")
    t1 = datetime(2026, 1, 1, 10, tzinfo=UTC)
    t2 = datetime(2026, 1, 1, 11, tzinfo=UTC)

    db_session.add_all(
        [
            DecisionRecordRow(
                decision_id="dec_a1",
                correlation_id="corr_a1",
                result="approved",
                state_snapshot_id="snap_1",
                decision_log=_decision_log(side="BUY"),
                mode="validation",
                experiment_id=exp_a,
                created_at=t1,
            ),
            DecisionRecordRow(
                decision_id="dec_a2",
                correlation_id="corr_a2",
                result="rejected",
                state_snapshot_id="snap_2",
                decision_log=_decision_log(side="HOLD"),
                mode="validation",
                experiment_id=exp_a,
                created_at=t2,
            ),
            DecisionRecordRow(
                decision_id="dec_b1",
                correlation_id="corr_b1",
                result="approved",
                state_snapshot_id="snap_3",
                decision_log=_decision_log(side="BUY"),
                mode="validation",
                experiment_id=exp_b,
                created_at=t1,
            ),
            DecisionRecordRow(
                decision_id="dec_b2",
                correlation_id="corr_b2",
                result="approved",
                state_snapshot_id="snap_4",
                decision_log=_decision_log(side="SELL"),
                mode="validation",
                experiment_id=exp_b,
                created_at=t2,
            ),
        ]
    )
    await db_session.commit()

    comparison = await compare_experiments(db_session, exp_a, exp_b)
    assert comparison.decision_diff_count == 1
    assert comparison.significant_cycles == ["corr_a2"]


@pytest.mark.asyncio
async def test_compare_experiments_no_shared_timestamps_means_no_diff(
    db_session: AsyncSession,
) -> None:
    exp_a = await _seed_experiment(db_session, "a")
    exp_b = await _seed_experiment(db_session, "b")

    db_session.add_all(
        [
            DecisionRecordRow(
                decision_id="dec_a1",
                correlation_id="corr_a1",
                result="approved",
                state_snapshot_id="snap_1",
                decision_log=_decision_log(side="BUY"),
                mode="validation",
                experiment_id=exp_a,
                created_at=datetime(2026, 1, 1, 10, tzinfo=UTC),
            ),
            DecisionRecordRow(
                decision_id="dec_b1",
                correlation_id="corr_b1",
                result="approved",
                state_snapshot_id="snap_2",
                decision_log=_decision_log(side="BUY"),
                mode="validation",
                experiment_id=exp_b,
                created_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
            ),
        ]
    )
    await db_session.commit()

    comparison = await compare_experiments(db_session, exp_a, exp_b)
    assert comparison.decision_diff_count == 0
    assert comparison.significant_cycles == []
