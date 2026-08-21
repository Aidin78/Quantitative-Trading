from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.governance import Hypothesis
from src.db.models import HypothesisRow


def _row_to_hypothesis(row: HypothesisRow) -> Hypothesis:
    return Hypothesis(
        hypothesis_id=row.hypothesis_id,
        observation=row.observation,
        statement=row.statement,
        expected_effect=row.expected_effect,
        proposed_change=row.proposed_change,
        source_experiment_run_id=row.source_experiment_run_id,
        tested_by_experiment_id=row.tested_by_experiment_id,
        status=row.status,  # type: ignore[arg-type]
        created_by=row.created_by,
        created_at=row.created_at,
    )


async def create_hypothesis(
    session: AsyncSession,
    *,
    observation: str,
    statement: str,
    expected_effect: str,
    proposed_change: str,
    source_experiment_run_id: str | None = None,
    created_by: str = "system",
) -> Hypothesis:
    row = HypothesisRow(
        hypothesis_id=f"hyp_{uuid.uuid4().hex[:12]}",
        observation=observation,
        statement=statement,
        expected_effect=expected_effect,
        proposed_change=proposed_change,
        source_experiment_run_id=source_experiment_run_id,
        tested_by_experiment_id=None,
        status="open",
        created_by=created_by,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return _row_to_hypothesis(row)


async def get_hypothesis(session: AsyncSession, hypothesis_id: str) -> Hypothesis | None:
    row = await session.get(HypothesisRow, hypothesis_id)
    if row is None:
        return None
    return _row_to_hypothesis(row)


async def list_hypotheses(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[Hypothesis]:
    stmt = select(HypothesisRow).order_by(HypothesisRow.created_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(HypothesisRow.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_hypothesis(row) for row in rows]


async def link_hypothesis_to_experiment(
    session: AsyncSession,
    hypothesis_id: str,
    *,
    experiment_id: str,
) -> Hypothesis | None:
    row = await session.get(HypothesisRow, hypothesis_id)
    if row is None:
        return None
    row.tested_by_experiment_id = experiment_id
    row.status = "tested"
    await session.flush()
    return _row_to_hypothesis(row)


async def resolve_hypothesis(
    session: AsyncSession,
    hypothesis_id: str,
    *,
    confirmed: bool,
) -> Hypothesis | None:
    row = await session.get(HypothesisRow, hypothesis_id)
    if row is None:
        return None
    row.status = "confirmed" if confirmed else "refuted"
    await session.flush()
    return _row_to_hypothesis(row)


def _tokenize(text: str) -> set[str]:
    return {token for token in text.lower().split() if len(token) > 2}


async def search_similar_hypotheses(
    session: AsyncSession,
    proposed_change: str,
    *,
    min_overlap: float = 0.5,
    limit: int = 10,
) -> list[Hypothesis]:
    """Find prior hypotheses whose proposed_change overlaps this one, so a
    researcher (or an LLM drafting a new hypothesis) can see whether an
    equivalent idea was already tested before spending a validation run on it.

    Deliberately a simple token-overlap heuristic rather than embeddings or
    full-text search infrastructure -- this only needs to catch near-duplicate
    proposals ("reduce momentum exposure above 80th vol percentile" vs
    "disable momentum signals in high volatility"), not rank arbitrary
    semantic similarity. A real similarity search can replace this later
    without changing the call site's contract (still returns a plain list).
    """
    query_tokens = _tokenize(proposed_change)
    if not query_tokens:
        return []

    rows = (await session.execute(select(HypothesisRow))).scalars().all()
    scored: list[tuple[float, HypothesisRow]] = []
    for row in rows:
        candidate_tokens = _tokenize(row.proposed_change)
        if not candidate_tokens:
            continue
        overlap = len(query_tokens & candidate_tokens) / len(query_tokens | candidate_tokens)
        if overlap >= min_overlap:
            scored.append((overlap, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [_row_to_hypothesis(row) for _, row in scored[:limit]]
