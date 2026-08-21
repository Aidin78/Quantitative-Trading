from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import DecisionRecordRow, ExperimentRunRow

# Metrics both experiments must have in metrics_summary for a meaningful delta.
# Kept in sync with what validation.job_runner.run_validation_job actually
# writes -- widening that dict widens this automatically, since deltas are
# just "every key present on both sides", not a fixed allowlist.


@dataclass(frozen=True)
class ExperimentComparison:
    experiment_a_id: str
    experiment_b_id: str
    metrics_delta: dict[str, float] = field(default_factory=dict)
    decision_diff_count: int = 0
    significant_cycles: list[str] = field(default_factory=list)
    a_run_count: int = 0
    b_run_count: int = 0


def _latest_metrics_summary(runs: list[ExperimentRunRow]) -> dict[str, float]:
    completed = [r for r in runs if r.status == "completed" and r.metrics_summary]
    if not completed:
        return {}
    latest = max(completed, key=lambda r: r.completed_at or r.started_at)
    return dict(latest.metrics_summary or {})


def _compute_metrics_delta(
    metrics_a: dict[str, float], metrics_b: dict[str, float]
) -> dict[str, float]:
    shared_keys = set(metrics_a) & set(metrics_b)
    return {key: round(metrics_b[key] - metrics_a[key], 6) for key in sorted(shared_keys)}


def _decision_side(decision_log: dict) -> str:
    result = decision_log.get("aggregation", {}).get("side")
    return result or "HOLD"


def _diff_decisions(
    decisions_a: list[DecisionRecordRow],
    decisions_b: list[DecisionRecordRow],
) -> tuple[int, list[str]]:
    """Match decisions from two experiments by timestamp (not correlation_id --
    each validation run generates its own random correlation_ids per cycle,
    so the same bar produces a different id in each run) and count how many
    cycles landed on a different result or side.
    """
    by_time_a = {row.created_at: row for row in decisions_a}
    by_time_b = {row.created_at: row for row in decisions_b}
    shared_times = sorted(set(by_time_a) & set(by_time_b))

    diff_count = 0
    significant: list[str] = []
    for ts in shared_times:
        row_a, row_b = by_time_a[ts], by_time_b[ts]
        result_changed = row_a.result != row_b.result
        side_changed = _decision_side(row_a.decision_log) != _decision_side(row_b.decision_log)
        if result_changed or side_changed:
            diff_count += 1
            significant.append(row_a.correlation_id)
    return diff_count, significant


async def compare_experiments(
    session: AsyncSession,
    experiment_a_id: str,
    experiment_b_id: str,
) -> ExperimentComparison:
    runs_a = (
        (
            await session.execute(
                select(ExperimentRunRow).where(ExperimentRunRow.experiment_id == experiment_a_id)
            )
        )
        .scalars()
        .all()
    )
    runs_b = (
        (
            await session.execute(
                select(ExperimentRunRow).where(ExperimentRunRow.experiment_id == experiment_b_id)
            )
        )
        .scalars()
        .all()
    )

    metrics_delta = _compute_metrics_delta(
        _latest_metrics_summary(list(runs_a)), _latest_metrics_summary(list(runs_b))
    )

    decisions_a = (
        (
            await session.execute(
                select(DecisionRecordRow).where(DecisionRecordRow.experiment_id == experiment_a_id)
            )
        )
        .scalars()
        .all()
    )
    decisions_b = (
        (
            await session.execute(
                select(DecisionRecordRow).where(DecisionRecordRow.experiment_id == experiment_b_id)
            )
        )
        .scalars()
        .all()
    )
    decision_diff_count, significant_cycles = _diff_decisions(list(decisions_a), list(decisions_b))

    return ExperimentComparison(
        experiment_a_id=experiment_a_id,
        experiment_b_id=experiment_b_id,
        metrics_delta=metrics_delta,
        decision_diff_count=decision_diff_count,
        significant_cycles=significant_cycles,
        a_run_count=len(runs_a),
        b_run_count=len(runs_b),
    )
