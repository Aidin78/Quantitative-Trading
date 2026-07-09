from __future__ import annotations

import asyncio
import csv
import io
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.services.validation_runner import (
    format_validation_error,
    new_validation_job_id,
    run_validation_job,
)
from src.api.services.validation_service import job_response, validation_jobs
from src.core.settings import load_app_yaml_config
from src.db.models import BacktestRunRow, ConfigRevisionRow, SimulatedTradeRow
from src.db.repositories.backtest import delete_validation_run, delete_validation_runs
from src.observability.metrics import VALIDATION_RUNS_TOTAL
from src.validation.harness import ValidationProgressEvent
from src.validation.trades import build_trade_ledger
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
    source: Literal["exchange", "csv"] = "exchange"
    initial_capital: float = 10000.0
    experiment_id: str | None = None
    revision_id: str | None = None


class WalkForwardRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    source: Literal["exchange", "csv"] = "exchange"
    initial_capital: float = 10000.0
    windows: int = 3
    train_ratio: float = 0.7


class ValidationRunsBulkDeleteRequest(BaseModel):
    run_ids: list[str]


async def _execute_job(job_id: str, body: ValidationRunRequest) -> None:
    job = validation_jobs.get(job_id)
    if job is None:
        return
    job.status = "running"
    job.message = "Starting validation job…"
    validation_jobs.update(job)

    async def on_progress(event: ValidationProgressEvent) -> None:
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
    except Exception as exc:
        job.status = "failed"
        job.error = format_validation_error(exc)
        job.message = job.error
        VALIDATION_RUNS_TOTAL.labels(status="failed").inc()
    validation_jobs.update(job)


@router.post("/run")
async def start_validation(body: ValidationRunRequest) -> dict:
    job_id = new_validation_job_id()
    validation_jobs.create(job_id, body.model_dump())
    asyncio.create_task(_execute_job(job_id, body))
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


_COMPARE_METRICS = (
    "total_trades",
    "win_rate",
    "return_pct",
    "score",
    "sharpe_ratio",
    "profit_factor",
    "max_drawdown_pct",
    "total_pnl",
)


def _run_summary(row: BacktestRunRow) -> dict:
    outcome = row.metrics.get("outcome", {}) if row.metrics else {}
    config = row.config or {}
    return {
        "run_id": row.run_id,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "start": config.get("start"),
        "end": config.get("end"),
        "initial_capital": config.get("initial_capital"),
        "revision_id": config.get("revision_id"),
        "experiment_id": config.get("experiment_id"),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "total_trades": outcome.get("total_trades", 0),
        "win_rate": outcome.get("win_rate", 0),
        "return_pct": outcome.get("return_pct", 0),
        "score": outcome.get("score", 0),
        "total_pnl": outcome.get("total_pnl", 0),
    }


def _revision_summary(revision: ConfigRevisionRow | None) -> dict | None:
    if revision is None:
        return None
    return {
        "revision_id": revision.revision_id,
        "label": revision.label,
        "engine_config_hash": revision.engine_config_hash,
        "features_config_hash": revision.features_config_hash,
        "providers_config_hash": revision.providers_config_hash,
        "risk_limits_hash": revision.risk_limits_hash,
        "fill_model_id": revision.fill_model_id,
        "parent_revision_id": revision.parent_revision_id,
    }


@router.get("/runs")
async def list_validation_runs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    symbol: str | None = None,
) -> dict:
    stmt = select(BacktestRunRow).order_by(BacktestRunRow.completed_at.desc())
    if symbol:
        stmt = stmt.where(BacktestRunRow.symbol == symbol)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "items": [_run_summary(row) for row in rows],
        "total": len(rows),
        "limit": limit,
        "offset": offset,
    }


@router.post("/runs/bulk-delete")
async def bulk_delete_validation_runs(
    body: ValidationRunsBulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not body.run_ids:
        raise HTTPException(status_code=400, detail="run_ids must not be empty")
    deleted, not_found = await delete_validation_runs(db, body.run_ids)
    await db.commit()
    return {
        "deleted": deleted,
        "not_found": not_found,
        "deleted_count": len(deleted),
    }


@router.delete("/runs/{run_id}")
async def delete_validation_run_route(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    removed = await delete_validation_run(db, run_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Validation run not found")
    await db.commit()
    return {"deleted": run_id}


@router.get("/compare")
async def compare_validation_runs(
    a: str = Query(..., description="First run_id"),
    b: str = Query(..., description="Second run_id"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row_a = await db.get(BacktestRunRow, a)
    row_b = await db.get(BacktestRunRow, b)
    if row_a is None or row_b is None:
        raise HTTPException(status_code=404, detail="One or both validation runs not found")

    outcome_a = row_a.metrics.get("outcome", {}) if row_a.metrics else {}
    outcome_b = row_b.metrics.get("outcome", {}) if row_b.metrics else {}
    metrics: dict[str, dict] = {}
    for key in _COMPARE_METRICS:
        val_a = float(outcome_a.get(key, 0))
        val_b = float(outcome_b.get(key, 0))
        if key == "max_drawdown_pct":
            winner = "a" if val_a < val_b else "b" if val_b < val_a else "tie"
        else:
            winner = "a" if val_a > val_b else "b" if val_b > val_a else "tie"
        metrics[key] = {
            "a": val_a,
            "b": val_b,
            "delta": val_b - val_a,
            "winner": winner,
        }

    rev_a_id = (row_a.config or {}).get("revision_id")
    rev_b_id = (row_b.config or {}).get("revision_id")
    rev_a = await db.get(ConfigRevisionRow, rev_a_id) if rev_a_id else None
    rev_b = await db.get(ConfigRevisionRow, rev_b_id) if rev_b_id else None

    revision_diff: dict | None = None
    if rev_a or rev_b:
        revision_diff = {
            "a": _revision_summary(rev_a),
            "b": _revision_summary(rev_b),
            "same_revision": rev_a_id == rev_b_id if rev_a_id and rev_b_id else False,
            "engine_hash_match": (
                rev_a.engine_config_hash == rev_b.engine_config_hash if rev_a and rev_b else None
            ),
            "providers_hash_match": (
                rev_a.providers_config_hash == rev_b.providers_config_hash
                if rev_a and rev_b
                else None
            ),
        }

    return {
        "a": _run_summary(row_a),
        "b": _run_summary(row_b),
        "metrics": metrics,
        "overall_winner": "a"
        if float(outcome_a.get("score", 0)) > float(outcome_b.get("score", 0))
        else "b"
        if float(outcome_b.get("score", 0)) > float(outcome_a.get("score", 0))
        else "tie",
        "revision_diff": revision_diff,
    }


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
