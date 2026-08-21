from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.governance import Candidate, CandidateCheck, CandidateEvaluation
from src.db.models import CandidateEvaluationRow, CandidateRow, ExperimentRow
from src.governance.candidate_evaluator import evaluate_candidate
from src.validation.optimization_scoring import OptimizationResult


def _row_to_candidate(row: CandidateRow) -> Candidate:
    return Candidate(
        candidate_id=row.candidate_id,
        experiment_id=row.experiment_id,
        hypothesis_id=row.hypothesis_id,
        parent_candidate_id=row.parent_candidate_id,
        state=row.state,  # type: ignore[arg-type]
        created_at=row.created_at,
    )


def _row_to_evaluation(row: CandidateEvaluationRow) -> CandidateEvaluation:
    return CandidateEvaluation(
        evaluation_id=row.evaluation_id,
        candidate_id=row.candidate_id,
        checks=tuple(CandidateCheck(**check) for check in row.checks),
        decision=row.decision,  # type: ignore[arg-type]
        decision_reason=row.decision_reason,
        created_at=row.created_at,
    )


async def create_candidate(
    session: AsyncSession,
    *,
    experiment_id: str,
    hypothesis_id: str | None = None,
    parent_candidate_id: str | None = None,
) -> Candidate:
    row = CandidateRow(
        candidate_id=f"cand_{uuid.uuid4().hex[:12]}",
        experiment_id=experiment_id,
        hypothesis_id=hypothesis_id,
        parent_candidate_id=parent_candidate_id,
        state="candidate",
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return _row_to_candidate(row)


async def get_candidate(session: AsyncSession, candidate_id: str) -> Candidate | None:
    row = await session.get(CandidateRow, candidate_id)
    if row is None:
        return None
    return _row_to_candidate(row)


async def list_candidates(
    session: AsyncSession,
    *,
    state: str | None = None,
    limit: int = 50,
) -> list[Candidate]:
    stmt = select(CandidateRow).order_by(CandidateRow.created_at.desc()).limit(limit)
    if state is not None:
        stmt = stmt.where(CandidateRow.state == state)
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_candidate(row) for row in rows]


async def run_candidate_evaluation(
    session: AsyncSession,
    candidate_id: str,
    optimization_result: OptimizationResult,
) -> CandidateEvaluation | None:
    """Run the deterministic acceptance policy against a candidate's
    OptimizationResult, persist the evaluation, and move the candidate to
    "rejected" on failure. Acceptance does NOT auto-promote the candidate to
    challenger/champion -- see promote_candidate for that separate,
    explicit step.
    """
    candidate_row = await session.get(CandidateRow, candidate_id)
    if candidate_row is None:
        return None

    checks, decision, decision_reason = evaluate_candidate(optimization_result)
    row = CandidateEvaluationRow(
        evaluation_id=f"caneval_{uuid.uuid4().hex[:12]}",
        candidate_id=candidate_id,
        checks=[check.model_dump(mode="json") for check in checks],
        decision=decision,
        decision_reason=decision_reason,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    if decision == "rejected":
        candidate_row.state = "rejected"
    await session.flush()
    return _row_to_evaluation(row)


async def list_candidate_evaluations(
    session: AsyncSession,
    candidate_id: str,
) -> list[CandidateEvaluation]:
    stmt = (
        select(CandidateEvaluationRow)
        .where(CandidateEvaluationRow.candidate_id == candidate_id)
        .order_by(CandidateEvaluationRow.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_evaluation(row) for row in rows]


_VALID_TRANSITIONS: dict[str, set[str]] = {
    "candidate": {"challenger", "rejected", "archived"},
    "challenger": {"champion", "rejected", "archived"},
    "champion": {"archived"},
    "rejected": {"archived"},
    "archived": set(),
}


async def promote_candidate(
    session: AsyncSession,
    candidate_id: str,
    *,
    to_state: str,
    require_accepted_evaluation: bool = True,
) -> Candidate | None:
    """Explicit state transition, separate from evaluation. A candidate is
    never promoted by evaluate_candidate() itself and never by having a
    higher historical return than the current champion -- promotion is this
    function, called deliberately, and (by default) blocked unless the
    candidate's most recent evaluation was "accepted".
    """
    row = await session.get(CandidateRow, candidate_id)
    if row is None:
        return None
    if to_state not in _VALID_TRANSITIONS.get(row.state, set()):
        raise ValueError(f"Cannot transition candidate from '{row.state}' to '{to_state}'")

    if require_accepted_evaluation and to_state in ("challenger", "champion"):
        evaluations = await list_candidate_evaluations(session, candidate_id)
        if not evaluations or evaluations[0].decision != "accepted":
            raise ValueError(
                "Cannot promote a candidate without a most-recent 'accepted' evaluation"
            )
        if to_state == "champion":
            other_champions = (
                (
                    await session.execute(
                        select(CandidateRow).where(CandidateRow.state == "champion")
                    )
                )
                .scalars()
                .all()
            )
            for champion_row in other_champions:
                champion_row.state = "archived"

    row.state = to_state
    await session.flush()
    return _row_to_candidate(row)


async def revision_has_candidate_lineage(session: AsyncSession, revision_id: str) -> bool:
    """Whether any Candidate traces back to this revision via its Experiment.
    Used to decide whether LiveGovernanceGate should apply the champion
    requirement at all -- a revision that never went through the candidate
    workflow (e.g. manual/legacy experiments) is not retroactively blocked.
    """
    stmt = (
        select(CandidateRow.candidate_id)
        .join(ExperimentRow, ExperimentRow.experiment_id == CandidateRow.experiment_id)
        .where(ExperimentRow.revision_id == revision_id)
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def revision_has_champion(session: AsyncSession, revision_id: str) -> bool:
    stmt = (
        select(CandidateRow.candidate_id)
        .join(ExperimentRow, ExperimentRow.experiment_id == CandidateRow.experiment_id)
        .where(ExperimentRow.revision_id == revision_id, CandidateRow.state == "champion")
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None
