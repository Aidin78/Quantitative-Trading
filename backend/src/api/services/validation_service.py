from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.api.services.job_persistence import (
    ACTIVE_STATUSES,
    JobPersistence,
    create_job_persistence,
)
from src.validation.harness import ValidationResult

NAMESPACE = "validation"


class JobCancelled(Exception):
    """Raised cooperatively when a validation job cancel is requested."""


@dataclass
class ValidationJob:
    id: str
    status: str
    config: dict
    result: ValidationResult | None = None
    result_snapshot: dict[str, Any] | None = None
    error: str | None = None
    phase: str = ""
    message: str = ""
    progress_current: int = 0
    progress_total: int = 0
    cancel_requested: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ValidationJobStore:
    def __init__(self, persistence: JobPersistence | None = None) -> None:
        self._jobs: dict[str, ValidationJob] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._persistence = persistence if persistence is not None else create_job_persistence()

    def create(self, job_id: str, config: dict) -> ValidationJob:
        job = ValidationJob(id=job_id, status="pending", config=config)
        self._jobs[job_id] = job
        self._persist(job)
        return job

    def get(self, job_id: str) -> ValidationJob | None:
        job = self._jobs.get(job_id)
        if job is not None:
            return job
        record = self._persistence.load(NAMESPACE, job_id)
        if record is None:
            return None
        hydrated = self._hydrate(record)
        self._jobs[job_id] = hydrated
        if record.get("status") in ACTIVE_STATUSES and hydrated.status == "failed":
            self._persist(hydrated)
        return hydrated

    def update(self, job: ValidationJob) -> None:
        job.updated_at = datetime.now(UTC)
        if job.result is not None:
            job.result_snapshot = {
                "engine_metrics": job.result.engine_metrics,
                "outcome_metrics": job.result.outcome_metrics,
                "run_id": job.result.run_id,
                "revision_id": job.result.revision_id,
                "experiment_id": job.result.experiment_id,
            }
        self._jobs[job.id] = job
        self._persist(job)
        from src.api.services.job_progress import job_progress

        job_progress.publish(job.id, job_response(job))

    def set_task(self, job_id: str, task: asyncio.Task[None]) -> None:
        self._tasks[job_id] = task

    def clear_task(self, job_id: str) -> None:
        self._tasks.pop(job_id, None)

    def has_active(self) -> bool:
        if any(j.status in ACTIVE_STATUSES for j in self._jobs.values()):
            return True
        return self._persistence.has_active(NAMESPACE)

    def request_cancel(self, job_id: str) -> ValidationJob | None:
        job = self.get(job_id)
        if job is None:
            return None
        if job.status not in ACTIVE_STATUSES:
            return job
        job.cancel_requested = True
        job.message = "Cancel requested…"
        self.update(job)
        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            task.cancel()
        return job

    def clear_local(self) -> None:
        """Drop process-local state (keeps persistence). Used to simulate restart."""
        self._jobs.clear()
        self._tasks.clear()

    def _persist(self, job: ValidationJob) -> None:
        self._persistence.save(NAMESPACE, job.id, self._serialize(job))

    def _serialize(self, job: ValidationJob) -> dict[str, Any]:
        snapshot = job.result_snapshot
        if snapshot is None and job.result is not None:
            snapshot = {
                "engine_metrics": job.result.engine_metrics,
                "outcome_metrics": job.result.outcome_metrics,
                "run_id": job.result.run_id,
                "revision_id": job.result.revision_id,
                "experiment_id": job.result.experiment_id,
            }
        return {
            "id": job.id,
            "status": job.status,
            "config": job.config,
            "error": job.error,
            "phase": job.phase,
            "message": job.message,
            "progress_current": job.progress_current,
            "progress_total": job.progress_total,
            "cancel_requested": job.cancel_requested,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "result_snapshot": snapshot,
        }

    def _hydrate(self, record: dict[str, Any]) -> ValidationJob:
        status = str(record.get("status", "failed"))
        error = record.get("error")
        message = str(record.get("message") or "")
        if status in ACTIVE_STATUSES:
            status = "failed"
            error = error or "Job interrupted by server restart"
            message = message or "Interrupted by server restart."
        return ValidationJob(
            id=str(record["id"]),
            status=status,
            config=dict(record.get("config") or {}),
            result=None,
            result_snapshot=record.get("result_snapshot"),
            error=error,
            phase=str(record.get("phase") or ""),
            message=message,
            progress_current=int(record.get("progress_current") or 0),
            progress_total=int(record.get("progress_total") or 0),
            cancel_requested=False,
            created_at=_parse_dt(record.get("created_at")),
            updated_at=_parse_dt(record.get("updated_at")),
        )


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return datetime.now(UTC)


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
    elif job.result_snapshot:
        payload.update(job.result_snapshot)
    return payload
