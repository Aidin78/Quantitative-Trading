"""Shared optimization sweep execution used by the API and durable worker."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from src.api.services.optimization_service import JobCancelled, optimization_sweeps
from src.validation.errors import format_validation_error
from src.validation.optimizer import OptimizationSpace, ProgressEvent, run_optimization


def _as_request(config: dict[str, Any] | Any) -> Any:
    from src.api.v1.optimization import OptimizationRunRequest

    if isinstance(config, OptimizationRunRequest):
        return config
    return OptimizationRunRequest.model_validate(config)


async def execute_optimization_sweep(
    sweep_id: str,
    config: dict[str, Any] | Any | None = None,
) -> None:
    """Run an optimization sweep and update ``optimization_sweeps`` through completion."""
    from src.core.settings import load_app_yaml_config

    sweep = optimization_sweeps.get(sweep_id)
    if sweep is None:
        return
    body = _as_request(config if config is not None else sweep.config)
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
        current = optimization_sweeps.get(sweep_id)
        if current is not None and current.cancel_requested:
            raise JobCancelled("Optimization sweep cancelled")
        sweep.progress_current = event.current
        sweep.progress_total = event.total
        sweep.phase = event.phase
        if event.phase in {"train", "refine"}:
            if event.stage == "start":
                label = "Refining" if event.phase == "refine" else "Training"
                sweep.message = event.detail or (
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
            max_parallel_trials=body.max_parallel_trials,
            on_progress=on_progress,
        )
        result.sweep_id = sweep_id
        sweep.result = result
        sweep.status = "completed"
    except (asyncio.CancelledError, JobCancelled):
        sweep.status = "cancelled"
        sweep.message = "Optimization cancelled."
        sweep.error = None
    except Exception as exc:
        sweep.status = "failed"
        sweep.error = format_validation_error(exc)
    finally:
        optimization_sweeps.clear_task(sweep_id)
        optimization_sweeps.update(sweep)
