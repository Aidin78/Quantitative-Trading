from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.services.validation_runner import new_validation_job_id, run_validation_job
from src.api.services.validation_service import validation_jobs
from src.core.settings import load_app_yaml_config
from src.db.models import BacktestRunRow
from src.observability.metrics import VALIDATION_RUNS_TOTAL
from src.validation.walk_forward import build_walk_forward_windows

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


class WalkForwardRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    windows: int = 3
    train_ratio: float = 0.7


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
        VALIDATION_RUNS_TOTAL.labels(status="completed").inc()
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        VALIDATION_RUNS_TOTAL.labels(status="failed").inc()
    validation_jobs.update(job)


@router.post("/run")
async def start_validation(body: ValidationRunRequest, background_tasks: BackgroundTasks) -> dict:
    job_id = new_validation_job_id()
    validation_jobs.create(job_id, body.model_dump())
    background_tasks.add_task(_execute_job, job_id, body)
    return {"id": job_id, "status": "pending"}


@router.post("/walk-forward")
async def walk_forward_validation(body: WalkForwardRequest) -> dict:
    app = load_app_yaml_config()
    sym = body.symbol or app.default_symbols[0]
    tf = body.timeframe or app.timeframes[0]
    start = datetime.fromisoformat(body.start_date or app.validation.default_start).replace(
        tzinfo=UTC
    )
    end = datetime.now(UTC)
    if body.end_date:
        end = datetime.fromisoformat(body.end_date).replace(tzinfo=UTC)
    windows = build_walk_forward_windows(
        start, end, windows=body.windows, train_ratio=body.train_ratio
    )
    results: list[dict] = []
    for window in windows:
        try:
            result = await run_validation_job(
                symbol=sym,
                timeframe=tf,
                start_date=window.test_start.date().isoformat(),
                end_date=window.test_end.date().isoformat(),
                persist_db=False,
            )
            results.append(
                {
                    "window": window.index,
                    "test_start": window.test_start.isoformat(),
                    "test_end": window.test_end.isoformat(),
                    "engine_metrics": result.engine_metrics,
                    "outcome_metrics": result.outcome_metrics,
                    "status": "completed",
                }
            )
            VALIDATION_RUNS_TOTAL.labels(status="completed").inc()
        except Exception as exc:
            results.append(
                {
                    "window": window.index,
                    "test_start": window.test_start.isoformat(),
                    "test_end": window.test_end.isoformat(),
                    "status": "failed",
                    "error": str(exc),
                }
            )
            VALIDATION_RUNS_TOTAL.labels(status="failed").inc()
    return {"symbol": sym, "timeframe": tf, "windows": results}


@router.get("/{job_id}/export")
async def export_validation(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    format: str = Query("csv"),
) -> StreamingResponse:
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only csv format supported")
    job = validation_jobs.get(job_id)
    data: dict
    if job and job.result:
        data = {
            "id": job_id,
            "engine_metrics": job.result.engine_metrics,
            "outcome_metrics": job.result.outcome_metrics,
            "revision_id": job.result.revision_id,
            "experiment_id": job.result.experiment_id,
        }
    else:
        row = await db.get(BacktestRunRow, job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Validation job not found")
        data = {
            "id": row.run_id,
            "config": row.config,
            "engine_metrics": row.metrics.get("engine", {}),
            "outcome_metrics": row.metrics.get("outcome", {}),
        }
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["key", "value"])
    for key, value in data.items():
        writer.writerow([key, value])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=validation_{job_id}.csv"},
    )


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
