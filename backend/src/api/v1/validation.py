from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.services.validation_runner import new_validation_job_id, run_validation_job
from src.api.services.validation_service import validation_jobs
from src.db.models import BacktestRunRow

router = APIRouter(
    prefix="/validation", tags=["validation"], dependencies=[Depends(get_current_user)]
)


class ValidationRunRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    csv_path: str | None = None
    experiment_id: str | None = None
    revision_id: str | None = None


async def _execute_job(job_id: str, body: ValidationRunRequest) -> None:
    job = validation_jobs.get(job_id)
    if job is None:
        return
    job.status = "running"
    validation_jobs.update(job)
    try:
        result = await run_validation_job(
            symbol=body.symbol,
            timeframe=body.timeframe,
            start_date=body.start_date,
            end_date=body.end_date,
            csv_path=body.csv_path,
            persist_db=True,
            experiment_id=body.experiment_id,
            revision_id=body.revision_id,
        )
        job.result = result
        job.status = "completed"
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
    validation_jobs.update(job)


@router.post("/run")
async def start_validation(body: ValidationRunRequest, background_tasks: BackgroundTasks) -> dict:
    job_id = new_validation_job_id()
    validation_jobs.create(job_id, body.model_dump())
    background_tasks.add_task(_execute_job, job_id, body)
    return {"id": job_id, "status": "pending"}


@router.get("/{job_id}")
async def get_validation(job_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    job = validation_jobs.get(job_id)
    if job is not None:
        if job.status in ("pending", "running"):
            return {"id": job_id, "status": job.status, "config": job.config}
        if job.status == "failed":
            return {"id": job_id, "status": "failed", "error": job.error}
        if job.result:
            return {
                "id": job_id,
                "status": "completed",
                "engine_metrics": job.result.engine_metrics,
                "outcome_metrics": job.result.outcome_metrics,
                "run_id": job.result.run_id,
                "revision_id": job.result.revision_id,
                "experiment_id": job.result.experiment_id,
            }

    row = await db.get(BacktestRunRow, job_id)
    if row is None:
        stmt = select(BacktestRunRow).where(BacktestRunRow.run_id == job_id)
        row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Validation job not found")
    return {
        "id": row.run_id,
        "status": "completed" if row.completed_at else "running",
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "config": row.config,
        "engine_metrics": row.metrics.get("engine", {}),
        "outcome_metrics": row.metrics.get("outcome", {}),
    }
