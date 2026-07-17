"""Shared validation job execution used by the API and durable worker."""

from __future__ import annotations

import asyncio
from typing import Any

from src.api.services.validation_service import JobCancelled, validation_jobs
from src.api.v1.validation_routes.schemas import ValidationRunRequest
from src.observability.metrics import VALIDATION_RUNS_TOTAL
from src.validation.errors import format_validation_error
from src.validation.harness import ValidationProgressEvent
from src.validation.job_runner import run_validation_job


def _as_request(config: dict[str, Any] | ValidationRunRequest) -> ValidationRunRequest:
    if isinstance(config, ValidationRunRequest):
        return config
    return ValidationRunRequest.model_validate(config)


async def execute_validation_job(
    job_id: str,
    config: dict[str, Any] | ValidationRunRequest | None = None,
) -> None:
    """Run a validation job and update ``validation_jobs`` through completion."""
    job = validation_jobs.get(job_id)
    if job is None:
        return
    body = _as_request(config if config is not None else job.config)
    job.status = "running"
    job.message = "Starting validation job…"
    validation_jobs.update(job)

    async def on_progress(event: ValidationProgressEvent) -> None:
        current = validation_jobs.get(job_id)
        if current is not None and current.cancel_requested:
            raise JobCancelled("Validation job cancelled")
        job.phase = event.phase
        job.message = event.message
        job.progress_current = event.current
        job.progress_total = event.total
        validation_jobs.update(job)

    try:
        result = await run_validation_job(
            symbol=body.symbol,
            timeframe=body.timeframe,
            start_date=body.start_date,
            end_date=body.end_date,
            csv_path=body.csv_path,
            source=body.source,
            initial_capital=body.initial_capital,
            persist_db=True,
            experiment_id=body.experiment_id,
            revision_id=body.revision_id,
            on_progress=on_progress,
        )
        job.result = result
        job.status = "completed"
        job.message = "Validation completed."
        VALIDATION_RUNS_TOTAL.labels(status="completed").inc()
    except (asyncio.CancelledError, JobCancelled):
        job.status = "cancelled"
        job.message = "Validation cancelled."
        job.error = None
        VALIDATION_RUNS_TOTAL.labels(status="cancelled").inc()
    except Exception as exc:
        job.status = "failed"
        job.error = format_validation_error(exc)
        job.message = job.error
        VALIDATION_RUNS_TOTAL.labels(status="failed").inc()
    finally:
        validation_jobs.clear_task(job_id)
        validation_jobs.update(job)
