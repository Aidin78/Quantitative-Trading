from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.validation.harness import ValidationResult


@dataclass
class ValidationJob:
    id: str
    status: str
    config: dict
    result: ValidationResult | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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
        self._jobs[job.id] = job


validation_jobs = ValidationJobStore()
