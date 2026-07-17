from __future__ import annotations

import asyncio
import csv
import io
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.api.services.job_progress import sse_job_event_stream
from src.api.services.validation_service import JobCancelled, job_response, validation_jobs
from src.api.v1.validation_routes.router import router
from src.api.v1.validation_routes.schemas import ValidationRunRequest, WalkForwardRequest
from src.core.settings import load_app_yaml_config
from src.db.models import BacktestRunRow, SimulatedTradeRow
from src.observability.metrics import VALIDATION_RUNS_TOTAL
from src.validation.errors import format_validation_error
from src.validation.harness import ValidationProgressEvent
from src.validation.job_runner import new_validation_job_id, run_validation_job
from src.validation.trades import build_trade_ledger
from src.validation.walk_forward import build_walk_forward_windows


async def _execute_job(job_id: str, body: ValidationRunRequest) -> None:
    job = validation_jobs.get(job_id)
    if job is None:
        return
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


@router.post("/run")
async def start_validation(body: ValidationRunRequest) -> dict:
    if validation_jobs.has_active():
        raise HTTPException(
            status_code=429,
            detail="A validation job is already running. Cancel it or wait for completion.",
        )
    job_id = new_validation_job_id()
    validation_jobs.create(job_id, body.model_dump())
    task = asyncio.create_task(_execute_job(job_id, body))
    validation_jobs.set_task(job_id, task)
    return {"id": job_id, "status": "pending"}


@router.post("/{job_id}/cancel")
async def cancel_validation(job_id: str) -> dict:
    job = validation_jobs.request_cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Validation job not found")
    if job.status not in {"pending", "running", "cancelled"}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in status '{job.status}'",
        )
    return {"id": job_id, "status": job.status, "message": job.message}


@router.get("/{job_id}/events")
async def validation_events(job_id: str) -> StreamingResponse:
    job = validation_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Validation job not found")
    initial = job_response(job)
    return StreamingResponse(
        sse_job_event_stream(job_id, initial=initial),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
                source=body.source,
                initial_capital=body.initial_capital,
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
                    "error": format_validation_error(exc),
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
    elif job and job.result_snapshot:
        data = {
            "id": job_id,
            "engine_metrics": job.result_snapshot.get("engine_metrics"),
            "outcome_metrics": job.result_snapshot.get("outcome_metrics"),
            "revision_id": job.result_snapshot.get("revision_id"),
            "experiment_id": job.result_snapshot.get("experiment_id"),
        }
    else:
        row = await db.get(BacktestRunRow, job_id)
        if row is None:
            stmt = select(BacktestRunRow).where(BacktestRunRow.run_id == job_id)
            row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Validation run not found. In-memory jobs are cleared when the "
                    "backend restarts — re-run the validation or open a saved run "
                    "from Run History."
                ),
            )
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


@router.get("/{job_id}/trades")
async def get_validation_trades(job_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    job = validation_jobs.get(job_id)
    if job is not None and job.result is not None:
        trades = build_trade_ledger(job.result.events)
        return {"run_id": job.result.run_id, "trades": trades, "total": len(trades)}

    row = await db.get(BacktestRunRow, job_id)
    if row is None:
        stmt = select(BacktestRunRow).where(BacktestRunRow.run_id == job_id)
        row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Validation job not found")

    stmt = (
        select(SimulatedTradeRow)
        .where(SimulatedTradeRow.run_id == row.run_id)
        .order_by(SimulatedTradeRow.trade_id)
    )
    trade_rows = (await db.execute(stmt)).scalars().all()
    trades = []
    for trade_row in trade_rows:
        payload = trade_row.payload or {}
        entry_price = float(payload.get("entry_price", 0))
        quantity = float(payload.get("quantity", 0))
        pnl = trade_row.pnl
        notional = entry_price * quantity
        trades.append(
            {
                "position_id": trade_row.position_id,
                "symbol": trade_row.symbol,
                "side": payload.get("side"),
                "entry_price": entry_price,
                "exit_price": float(payload.get("exit_price", 0)),
                "stop_loss": payload.get("stop_loss"),
                "take_profit": payload.get("take_profit"),
                "quantity": quantity,
                "exit_reason": trade_row.exit_reason,
                "pnl": pnl,
                "return_pct": (pnl / notional * 100) if notional > 0 else 0.0,
                "bars_held": payload.get("bars_held"),
                "exit_time": None,
                "win": pnl > 0,
            }
        )
    return {"run_id": row.run_id, "trades": trades, "total": len(trades)}


@router.get("/{job_id}")
async def get_validation(job_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    job = validation_jobs.get(job_id)
    if job is not None:
        return job_response(job)

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
