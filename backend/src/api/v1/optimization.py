from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.services.config_service import (
    write_engine_config,
    write_features_config,
    write_provider_config,
    write_validation_settings,
)
from src.api.services.optimization_service import (
    new_sweep_id,
    optimization_sweeps,
    result_to_dict,
    sweep_response,
)
from src.api.services.validation_runner import format_validation_error
from src.governance.revision_store import compute_config_revision, save_revision
from src.validation.optimizer import OptimizationSpace, ProgressEvent, run_optimization
from src.validation.trial_config import SESSION_PRESETS

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


class OptimizationApplyRequest(BaseModel):
    use_fallback: bool = False


def _apply_trial_params(params: dict[str, Any]) -> None:
    session_preset = str(params.get("session_preset", "eu_us"))
    allowed_sessions = list(SESSION_PRESETS.get(session_preset, SESSION_PRESETS["eu_us"]))
    engine_patch = {
        "aggregation": {
            "min_agreeing_providers": int(params["min_agreeing_providers"]),
        },
        "filter": {
            "min_atr_pct": float(params.get("min_atr_pct", 0.3)),
            "allowed_sessions": allowed_sessions,
        },
        "risk": {
            "min_confidence": float(params["min_confidence"]),
            "min_risk_reward": float(params["min_risk_reward"]),
            "max_signals_per_day": int(params.get("max_signals_per_day", 10)),
        },
    }
    write_engine_config(engine_patch)

    provider_ids = (
        "ema_crossover",
        "rsi_divergence",
        "macd_momentum",
        "adx_trend_strength",
        "bollinger_reversion",
    )
    for provider_id in provider_ids:
        if provider_id == "ema_crossover":
            enabled_key = "ema_enabled"
            weight_key = "ema_weight"
        elif provider_id == "rsi_divergence":
            enabled_key = "rsi_enabled"
            weight_key = "rsi_weight"
        elif provider_id == "macd_momentum":
            enabled_key = "macd_enabled"
            weight_key = "macd_weight"
        elif provider_id == "adx_trend_strength":
            enabled_key = "adx_enabled"
            weight_key = "adx_weight"
        else:
            enabled_key = "bb_enabled"
            weight_key = "bb_weight"
        enabled_default = 0 if provider_id in {"adx_trend_strength", "bollinger_reversion"} else 1
        provider_patch: dict[str, Any] = {
            "enabled": bool(int(params.get(enabled_key, enabled_default))),
            "weight": float(params.get(weight_key, 1.0)),
            "params": {
                "min_confidence": float(params["min_confidence"]),
                "sl_atr_mult": float(params["sl_atr_mult"]),
                "tp_atr_mult": float(params["tp_atr_mult"]),
            },
        }
        if provider_id == "rsi_divergence":
            provider_patch["params"]["oversold"] = float(params.get("oversold", 30.0))
            provider_patch["params"]["overbought"] = float(params.get("overbought", 70.0))
            provider_patch["params"]["avoid_high_vol"] = bool(int(params.get("avoid_high_vol", 1)))
        if provider_id == "ema_crossover":
            provider_patch["params"]["require_trend"] = bool(int(params.get("require_trend", 1)))
        if provider_id == "macd_momentum":
            provider_patch["params"]["require_signal_align"] = bool(
                int(params.get("require_signal_align", 1))
            )
            provider_patch["params"]["min_histogram_slope"] = float(
                params.get("min_histogram_slope", 0.0)
            )
            provider_patch["params"]["require_trend"] = bool(
                int(params.get("macd_require_trend", 0))
            )
        if provider_id == "adx_trend_strength":
            provider_patch["params"]["min_adx"] = float(params.get("min_adx", 25.0))
            provider_patch["params"]["min_di_spread"] = float(params.get("min_di_spread", 5.0))
            provider_patch["params"]["require_trend"] = bool(
                int(params.get("adx_require_trend", 0))
            )
        if provider_id == "bollinger_reversion":
            provider_patch["params"]["avoid_high_vol"] = bool(
                int(params.get("bb_avoid_high_vol", 1))
            )
            provider_patch["params"]["max_adx"] = float(params.get("bb_max_adx", 0.0))
        write_provider_config(provider_id, provider_patch)

    write_validation_settings(
        {
            "max_bars_in_trade": int(params["max_bars_in_trade"]),
            "risk_pct_per_trade": float(params.get("risk_pct_per_trade", 1.0)),
        }
    )
    write_features_config(
        ema_fast=int(params.get("ema_fast", 12)),
        ema_slow=int(params.get("ema_slow", 26)),
        rsi_period=int(params.get("rsi_period", 14)),
        macd_fast=int(params.get("macd_fast", 12)),
        macd_slow=int(params.get("macd_slow", 26)),
        macd_signal_period=int(params.get("macd_signal_period", 9)),
        adx_period=int(params.get("adx_period", 14)),
        bb_period=int(params.get("bb_period", 20)),
        bb_std=float(params.get("bb_std", 2.0)),
    )


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

    async def on_progress(event: ProgressEvent) -> None:
        sweep.progress_current = event.current
        sweep.progress_total = event.total
        sweep.phase = event.phase
        if event.phase in {"train", "refine"}:
            if event.stage == "start":
                label = "Refining" if event.phase == "refine" else "Training"
                sweep.message = (
                    f"{label} candidate {event.current + 1} of "
                    f"{event.train_count} on in-sample data…"
                )
            else:
                sweep.message = (
                    f"Finished evaluating candidate {event.current} of " f"{event.train_count}."
                )
                if event.trial is not None:
                    sweep.live_trials.append(event.trial)
        else:
            done_test = max(0, event.current - event.train_count)
            if event.stage == "start":
                sweep.message = (
                    f"Validating top candidate {done_test + 1} of "
                    f"{event.test_count} on held-out test data…"
                )
            else:
                sweep.message = f"Validated {done_test} of {event.test_count} finalists."
        optimization_sweeps.update(sweep)

    try:
        min_trades_holdout = body.min_trades_holdout
        if min_trades_holdout is None:
            min_trades_holdout = app.optimization.min_trades_holdout
        min_trades = body.min_trades or app.optimization.min_trades_test

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
            seed=body.seed,
            min_trades=min_trades,
            min_return_pct=body.min_return_pct,
            holdout_ratio=body.holdout_ratio,
            walk_forward_windows=body.walk_forward_windows,
            walk_forward_mode=body.walk_forward_mode,
            local_refine=body.local_refine,
            search_method=body.search_method,
            min_trades_holdout=min_trades_holdout,
            on_progress=on_progress,
        )
        result.sweep_id = sweep_id
        sweep.result = result
        sweep.status = "completed"
    except Exception as exc:
        sweep.status = "failed"
        sweep.error = format_validation_error(exc)
    optimization_sweeps.update(sweep)


@router.post("/run")
async def start_optimization(
    body: OptimizationRunRequest,
) -> dict:
    sweep_id = new_sweep_id()
    optimization_sweeps.create(sweep_id, body.model_dump())
    asyncio.create_task(_execute_sweep(sweep_id, body))
    return {"id": sweep_id, "status": "pending"}


@router.get("/{sweep_id}")
async def get_optimization(sweep_id: str) -> dict:
    sweep = optimization_sweeps.get(sweep_id)
    if sweep is None:
        raise HTTPException(status_code=404, detail="Optimization sweep not found")
    return sweep_response(sweep)


@router.post("/{sweep_id}/apply")
async def apply_optimization_best(
    sweep_id: str,
    body: OptimizationApplyRequest = OptimizationApplyRequest(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sweep = optimization_sweeps.get(sweep_id)
    if sweep is None or sweep.result is None:
        raise HTTPException(status_code=404, detail="No completed optimization sweep found")

    use_fallback = body.use_fallback
    applied_from = "best"
    if sweep.result.best_valid and sweep.result.best is not None:
        params = sweep.result.best.params
    elif use_fallback and sweep.result.fallback_trial is not None:
        params = sweep.result.fallback_trial.params
        applied_from = "fallback"
    else:
        raise HTTPException(
            status_code=400,
            detail=sweep.result.selection_message
            or (
                "No valid best configuration. "
                "Pass use_fallback=true to apply the closest candidate."
            ),
        )

    _apply_trial_params(params)

    revision = compute_config_revision(label=f"optimizer_apply_{sweep_id}")
    await save_revision(db, revision)
    await db.commit()

    trial_payload = (
        result_to_dict(sweep.result)["best"]
        if applied_from == "best"
        else result_to_dict(sweep.result).get("fallback_trial")
    )

    return {
        "sweep_id": sweep_id,
        "revision_id": revision.revision_id,
        "applied_params": params,
        "applied_from": applied_from,
        "best": trial_payload,
        "holdout_start": sweep.result.holdout_start.isoformat()
        if sweep.result.holdout_start
        else None,
        "holdout_end": sweep.result.holdout_end.isoformat() if sweep.result.holdout_end else None,
    }
