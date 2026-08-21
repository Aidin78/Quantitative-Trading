from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

# Deliberately lighter than ValidationJobStore: one Claude call takes seconds,
# not minutes, has no meaningful per-step progress to stream, and doesn't need
# Redis-queue durability across a restart -- a plain in-memory dict is enough
# for "did it finish, and what/why".


@dataclass
class HypothesisGenerationJob:
    id: str
    run_id: str
    status: str = "pending"
    hypothesis_id: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class HypothesisGenerationJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, HypothesisGenerationJob] = {}

    def create(self, run_id: str) -> HypothesisGenerationJob:
        job = HypothesisGenerationJob(id=f"hgen_{uuid.uuid4().hex[:12]}", run_id=run_id)
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> HypothesisGenerationJob | None:
        return self._jobs.get(job_id)

    def mark_completed(self, job_id: str, hypothesis_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = "completed"
        job.hypothesis_id = hypothesis_id
        job.updated_at = datetime.now(UTC)

    def mark_failed(self, job_id: str, error: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = "failed"
        job.error = error
        job.updated_at = datetime.now(UTC)

    def mark_running(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = "running"
        job.updated_at = datetime.now(UTC)


hypothesis_generation_jobs = HypothesisGenerationJobStore()


async def run_hypothesis_generation_job(job_id: str, run_id: str) -> None:
    from sqlalchemy import select

    from src.db.models import BacktestRunRow
    from src.db.session import get_session_factory
    from src.governance.hypothesis_generator import (
        HypothesisGenerationError,
        generate_and_store_hypothesis,
    )

    hypothesis_generation_jobs.mark_running(job_id)
    try:
        async with get_session_factory()() as session:
            row = await session.get(BacktestRunRow, run_id)
            if row is None:
                stmt = select(BacktestRunRow).where(BacktestRunRow.run_id == run_id)
                row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                raise HypothesisGenerationError(f"Backtest run not found: {run_id}")

            outcome = (row.metrics or {}).get("outcome", {})
            failure_summary = outcome.get("failure_summary")
            if not failure_summary:
                raise HypothesisGenerationError(
                    f"Backtest run {run_id} has no failure_summary "
                    "(re-run validation to compute one)"
                )

            hypothesis = await generate_and_store_hypothesis(session, failure_summary)
            await session.commit()
        hypothesis_generation_jobs.mark_completed(job_id, hypothesis.hypothesis_id)
    except HypothesisGenerationError as exc:
        hypothesis_generation_jobs.mark_failed(job_id, str(exc))
    except Exception as exc:  # noqa: BLE001
        hypothesis_generation_jobs.mark_failed(job_id, f"Unexpected error: {exc}")


def start_hypothesis_generation(run_id: str) -> HypothesisGenerationJob:
    job = hypothesis_generation_jobs.create(run_id)
    asyncio.create_task(run_hypothesis_generation_job(job.id, run_id))
    return job
