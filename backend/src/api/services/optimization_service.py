from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.validation.optimizer import OptimizationResult, TrialResult


@dataclass
class OptimizationSweep:
    id: str
    status: str
    config: dict[str, Any]
    result: OptimizationResult | None = None
    error: str | None = None
    progress_current: int = 0
    progress_total: int = 0
    phase: str = ""
    message: str = ""
    live_trials: list[TrialResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class OptimizationSweepStore:
    def __init__(self) -> None:
        self._sweeps: dict[str, OptimizationSweep] = {}

    def create(self, sweep_id: str, config: dict[str, Any]) -> OptimizationSweep:
        sweep = OptimizationSweep(id=sweep_id, status="pending", config=config)
        self._sweeps[sweep_id] = sweep
        return sweep

    def get(self, sweep_id: str) -> OptimizationSweep | None:
        return self._sweeps.get(sweep_id)

    def update(self, sweep: OptimizationSweep) -> None:
        sweep.updated_at = datetime.now(UTC)
        self._sweeps[sweep.id] = sweep


optimization_sweeps = OptimizationSweepStore()


def new_sweep_id() -> str:
    return f"sweep_{uuid.uuid4().hex[:12]}"


def _finite_metric(outcome: dict[str, Any], key: str) -> float | None:
    value = outcome.get(key)
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _return_pct(outcome: dict[str, Any]) -> float | None:
    direct = _finite_metric(outcome, "return_pct")
    if direct is not None:
        return direct
    initial = outcome.get("initial_capital")
    pnl = outcome.get("total_pnl")
    if initial is not None and pnl is not None:
        try:
            initial_f = float(initial)
            if initial_f > 0:
                derived = float(pnl) / initial_f * 100.0
                if math.isfinite(derived):
                    return derived
        except (TypeError, ValueError):
            pass
    if "total_trades" in outcome:
        return 0.0
    return None


def trial_to_dict(trial: TrialResult) -> dict[str, Any]:
    composite = trial.composite_score
    composite_export = composite if composite is not None and math.isfinite(composite) else None
    test_outcome = trial.test_outcome or {}
    train_outcome = trial.train_outcome or {}
    return {
        "trial_id": trial.trial_id,
        "params": trial.params,
        "train_score": trial.train_score,
        "test_score": trial.test_score,
        "stability": trial.stability,
        "composite_score": composite_export,
        "composite_eligible": composite_export is not None,
        "fold_scores": trial.fold_scores,
        "fold_std": trial.fold_std,
        "pareto_rank": trial.pareto_rank,
        "revision_id": trial.revision_id,
        "train_total_trades": train_outcome.get("total_trades"),
        "train_return_pct": _return_pct(train_outcome),
        "test_total_trades": test_outcome.get("total_trades")
        if trial.test_outcome is not None
        else None,
        "test_return_pct": _return_pct(test_outcome) if trial.test_outcome is not None else None,
    }


def result_to_dict(result: OptimizationResult) -> dict[str, Any]:
    return {
        "sweep_id": result.sweep_id,
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "train_start": result.train_start.isoformat(),
        "train_end": result.train_end.isoformat(),
        "test_start": result.test_start.isoformat(),
        "test_end": result.test_end.isoformat(),
        "holdout_start": result.holdout_start.isoformat() if result.holdout_start else None,
        "holdout_end": result.holdout_end.isoformat() if result.holdout_end else None,
        "optimization_end": result.optimization_end.isoformat()
        if result.optimization_end
        else None,
        "space": result.space.as_dict(),
        "trials": [trial_to_dict(t) for t in result.trials],
        "best": trial_to_dict(result.best) if result.best else None,
        "best_valid": result.best_valid,
        "selection_message": result.selection_message,
        "fallback_trial": trial_to_dict(result.fallback_trial) if result.fallback_trial else None,
    }


def sweep_response(sweep: OptimizationSweep) -> dict[str, Any]:
    elapsed = (sweep.updated_at - sweep.created_at).total_seconds()
    payload: dict[str, Any] = {
        "id": sweep.id,
        "status": sweep.status,
        "config": sweep.config,
        "phase": sweep.phase,
        "message": sweep.message,
        "elapsed_seconds": round(elapsed, 1),
        "progress": {
            "current": sweep.progress_current,
            "total": sweep.progress_total,
        },
    }
    if sweep.error:
        payload["error"] = sweep.error
    if sweep.result:
        payload.update(result_to_dict(sweep.result))
    elif sweep.live_trials:
        payload["trials"] = [trial_to_dict(t) for t in sweep.live_trials]
    return payload
