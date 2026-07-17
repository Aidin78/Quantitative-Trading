from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.services.config_service import (
    write_engine_config,
    write_features_config,
    write_provider_config,
    write_validation_settings,
)
from src.api.services.job_progress import sse_job_event_stream
from src.api.services.optimization_service import (
    new_sweep_id,
    optimization_sweeps,
    result_to_dict,
    sweep_response,
)
from src.governance.revision_store import compute_config_revision, save_revision
from src.validation.optimization_job_executor import execute_optimization_sweep
from src.validation.trial_config import (
    build_engine_write_patch,
    build_features_write_kwargs,
    build_provider_write_patches,
    build_validation_settings_patch,
)

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
    seed: int | None = None
    min_trades: int = Field(default=50, ge=0)
    min_return_pct: float = Field(default=0.0)
    min_trades_holdout: int | None = Field(default=None, ge=0)
    holdout_ratio: float = Field(default=0.2, ge=0.0, lt=0.5)
    walk_forward_windows: int = Field(default=1, ge=1, le=6)
    walk_forward_mode: Literal["fixed", "anchored"] = "anchored"
    local_refine: bool = True
    search_method: Literal["grid", "optuna"] = "grid"
    max_parallel_trials: int = Field(default=1, ge=1, le=8)


class OptimizationApplyRequest(BaseModel):
    use_fallback: bool = False


def _apply_trial_params(params: dict[str, Any]) -> None:
    """Persist a trial using the same mappers as in-memory optimization sweeps."""
    write_engine_config(build_engine_write_patch(params))
    for provider_id, provider_patch in build_provider_write_patches(params).items():
        write_provider_config(provider_id, provider_patch)
    write_validation_settings(build_validation_settings_patch(params))
    write_features_config(**build_features_write_kwargs(params))


# Re-export for tests that patch the route-module execution entrypoint.
_execute_sweep = execute_optimization_sweep


@router.post("/run")
async def start_optimization(
    body: OptimizationRunRequest,
) -> dict:
    if optimization_sweeps.has_active():
        raise HTTPException(
            status_code=429,
            detail="An optimization sweep is already running. Cancel it or wait for completion.",
        )
    sweep_id = new_sweep_id()
    optimization_sweeps.create(sweep_id, body.model_dump())
    if optimization_sweeps.uses_job_queue():
        optimization_sweeps.enqueue(sweep_id)
    else:
        task = asyncio.create_task(_execute_sweep(sweep_id, body))
        optimization_sweeps.set_task(sweep_id, task)
    return {"id": sweep_id, "status": "pending"}


@router.get("/{sweep_id}")
async def get_optimization(sweep_id: str) -> dict:
    sweep = optimization_sweeps.get(sweep_id)
    if sweep is None:
        raise HTTPException(status_code=404, detail="Optimization sweep not found")
    return sweep_response(sweep)


@router.get("/{sweep_id}/events")
async def optimization_events(sweep_id: str) -> StreamingResponse:
    sweep = optimization_sweeps.get(sweep_id)
    if sweep is None:
        raise HTTPException(status_code=404, detail="Optimization sweep not found")
    initial = sweep_response(sweep)
    return StreamingResponse(
        sse_job_event_stream(sweep_id, initial=initial),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{sweep_id}/cancel")
async def cancel_optimization(sweep_id: str) -> dict:
    sweep = optimization_sweeps.request_cancel(sweep_id)
    if sweep is None:
        raise HTTPException(status_code=404, detail="Optimization sweep not found")
    if sweep.status not in {"pending", "running", "cancelled"}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel sweep in status '{sweep.status}'",
        )
    return {"id": sweep_id, "status": sweep.status, "message": sweep.message}


@router.post("/{sweep_id}/apply")
async def apply_optimization_best(
    sweep_id: str,
    body: OptimizationApplyRequest = OptimizationApplyRequest(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sweep = optimization_sweeps.get(sweep_id)
    snapshot = (
        result_to_dict(sweep.result)
        if sweep is not None and sweep.result is not None
        else (sweep.result_snapshot if sweep is not None else None)
    )
    if sweep is None or snapshot is None:
        raise HTTPException(status_code=404, detail="No completed optimization sweep found")

    use_fallback = body.use_fallback
    applied_from = "best"
    best = snapshot.get("best")
    fallback = snapshot.get("fallback_trial")
    best_valid = bool(snapshot.get("best_valid"))
    if best_valid and best is not None:
        params = best["params"]
    elif use_fallback and fallback is not None:
        params = fallback["params"]
        applied_from = "fallback"
    else:
        raise HTTPException(
            status_code=400,
            detail=snapshot.get("selection_message")
            or (
                "No valid best configuration. "
                "Pass use_fallback=true to apply the closest candidate."
            ),
        )

    _apply_trial_params(params)

    revision = compute_config_revision(label=f"optimizer_apply_{sweep_id}")
    await save_revision(db, revision)
    await db.commit()

    trial_payload = best if applied_from == "best" else fallback

    return {
        "sweep_id": sweep_id,
        "revision_id": revision.revision_id,
        "applied_params": params,
        "applied_from": applied_from,
        "best": trial_payload,
        "holdout_start": snapshot.get("holdout_start"),
        "holdout_end": snapshot.get("holdout_end"),
    }
