from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.services.config_service import (
    write_engine_config,
    write_provider_config,
    write_validation_settings,
)
from src.api.services.optimization_service import (
    new_sweep_id,
    optimization_sweeps,
    result_to_dict,
    sweep_response,
)
from src.governance.revision_store import compute_config_revision, save_revision
from src.validation.optimizer import OptimizationSpace, run_optimization

router = APIRouter(
    prefix="/optimization", tags=["optimization"], dependencies=[Depends(get_current_user)]
)


class OptimizationRunRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    source: Literal["exchange", "csv"] = "csv"
    initial_capital: float = 10000.0
    train_ratio: float = Field(default=0.7, gt=0, lt=1)
    max_trials: int = Field(default=40, ge=1, le=200)
    top_k: int = Field(default=5, ge=1, le=20)
    space: dict[str, list[Any]] | None = None
    csv_path: str | None = None


async def _execute_sweep(sweep_id: str, body: OptimizationRunRequest) -> None:
    from src.core.settings import load_app_yaml_config

    sweep = optimization_sweeps.get(sweep_id)
    if sweep is None:
        return
    sweep.status = "running"
    optimization_sweeps.update(sweep)

    app = load_app_yaml_config()
    sym = body.symbol or app.default_symbols[0]
    tf = body.timeframe or app.timeframes[0]
    start = datetime.fromisoformat(body.start_date or app.validation.default_start).replace(
        tzinfo=UTC
    )
    end = datetime.now(UTC)
    if body.end_date:
        end = datetime.fromisoformat(body.end_date).replace(tzinfo=UTC)

    space = OptimizationSpace.from_dict(body.space)

    async def on_progress(current: int, total: int, _trial) -> None:
        sweep.progress_current = current
        sweep.progress_total = total
        optimization_sweeps.update(sweep)

    try:
        result = await run_optimization(
            symbol=sym,
            timeframe=tf,
            start=start,
            end=end,
            source=body.source,
            initial_capital=body.initial_capital,
            train_ratio=body.train_ratio,
            max_trials=body.max_trials,
            top_k=body.top_k,
            space=space,
            csv_path=body.csv_path,
            on_progress=on_progress,
        )
        result.sweep_id = sweep_id
        sweep.result = result
        sweep.status = "completed"
    except Exception as exc:
        sweep.status = "failed"
        sweep.error = str(exc)
    optimization_sweeps.update(sweep)


@router.post("/run")
async def start_optimization(
    body: OptimizationRunRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    sweep_id = new_sweep_id()
    optimization_sweeps.create(sweep_id, body.model_dump())
    background_tasks.add_task(_execute_sweep, sweep_id, body)
    return {"id": sweep_id, "status": "pending"}


@router.get("/{sweep_id}")
async def get_optimization(sweep_id: str) -> dict:
    sweep = optimization_sweeps.get(sweep_id)
    if sweep is None:
        raise HTTPException(status_code=404, detail="Optimization sweep not found")
    return sweep_response(sweep)


@router.post("/{sweep_id}/apply")
async def apply_optimization_best(sweep_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    sweep = optimization_sweeps.get(sweep_id)
    if sweep is None or sweep.result is None or sweep.result.best is None:
        raise HTTPException(status_code=404, detail="No completed optimization with a best trial")

    params = sweep.result.best.params
    engine_patch = {
        "aggregation": {
            "min_agreeing_providers": int(params["min_agreeing_providers"]),
        },
        "risk": {
            "min_confidence": float(params["min_confidence"]),
            "min_risk_reward": float(params["min_risk_reward"]),
        },
    }
    write_engine_config(engine_patch)

    provider_patch = {
        "params": {
            "min_confidence": float(params["min_confidence"]),
            "sl_atr_mult": float(params["sl_atr_mult"]),
            "tp_atr_mult": float(params["tp_atr_mult"]),
        }
    }
    for provider_id in ("ema_crossover", "rsi_divergence"):
        write_provider_config(provider_id, provider_patch)

    write_validation_settings(
        {
            "max_bars_in_trade": int(params["max_bars_in_trade"]),
        }
    )

    revision = compute_config_revision(label=f"optimizer_apply_{sweep_id}")
    await save_revision(db, revision)
    await db.commit()

    return {
        "sweep_id": sweep_id,
        "revision_id": revision.revision_id,
        "applied_params": params,
        "best": result_to_dict(sweep.result)["best"],
    }
