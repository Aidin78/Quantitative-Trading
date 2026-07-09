from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.validation.harness import ValidationResult


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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ValidationJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ValidationJob] = {}

    def create(self, job_id: str, config: dict) -> ValidationJob:
        job = ValidationJob(id=job_id, status="pending", config=config)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> ValidationJob | None:
        return self._jobs.get(job_id)

    def update(self, job: ValidationJob) -> None:
        job.updated_at = datetime.now(UTC)
        self._jobs[job.id] = job


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
