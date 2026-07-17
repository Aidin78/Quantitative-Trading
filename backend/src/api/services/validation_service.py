from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.validation.harness import ValidationResult


class JobCancelled(Exception):
    """Raised cooperatively when a validation job cancel is requested."""


@dataclass
class ValidationJob:
    id: str
    status: str
    config: dict
    result: ValidationResult | None = None
    error: str | None = None
    phase: str = ""
    message: str = ""
    progress_current: int = 0
    progress_total: int = 0
    cancel_requested: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ValidationJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ValidationJob] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def create(self, job_id: str, config: dict) -> ValidationJob:
        job = ValidationJob(id=job_id, status="pending", config=config)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> ValidationJob | None:
        return self._jobs.get(job_id)

    def update(self, job: ValidationJob) -> None:
        job.updated_at = datetime.now(UTC)
        self._jobs[job.id] = job

    def set_task(self, job_id: str, task: asyncio.Task[None]) -> None:
        self._tasks[job_id] = task

    def clear_task(self, job_id: str) -> None:
        self._tasks.pop(job_id, None)

    def has_active(self) -> bool:
        return any(j.status in {"pending", "running"} for j in self._jobs.values())

    def request_cancel(self, job_id: str) -> ValidationJob | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if job.status not in {"pending", "running"}:
            return job
        job.cancel_requested = True
        job.message = "Cancel requested…"
        self.update(job)
        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            task.cancel()
        return job


validation_jobs = ValidationJobStore()


def job_response(job: ValidationJob) -> dict[str, Any]:
    elapsed = (job.updated_at - job.created_at).total_seconds()
    payload: dict[str, Any] = {
        "id": job.id,
        "status": job.status,
        "config": job.config,
        "phase": job.phase,
        "message": job.message,
        "elapsed_seconds": round(elapsed, 1),
        "progress": {
            "current": job.progress_current,
            "total": job.progress_total,
        },
    }
    if job.error:
        payload["error"] = job.error
    if job.result:
        payload.update(
            {
                "engine_metrics": job.result.engine_metrics,
                "outcome_metrics": job.result.outcome_metrics,
                "run_id": job.result.run_id,
                "revision_id": job.result.revision_id,
                "experiment_id": job.result.experiment_id,
            }
        )
    return payload
