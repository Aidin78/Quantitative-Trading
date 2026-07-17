from __future__ import annotations

from fastapi import Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.api.v1.validation_routes.router import router
from src.api.v1.validation_routes.schemas import ValidationRunsBulkDeleteRequest
from src.db.models import BacktestRunRow, ConfigRevisionRow
from src.db.repositories.backtest import delete_validation_run, delete_validation_runs

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
