from __future__ import annotations

import asyncio
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.api.services.job_persistence import (
    ACTIVE_STATUSES,
    JobPersistence,
    create_job_persistence,
)
from src.validation.optimizer import OptimizationResult, TrialResult

NAMESPACE = "optimization"


class JobCancelled(Exception):
    """Raised cooperatively when a sweep cancel is requested."""


@dataclass
class OptimizationSweep:
    id: str
    status: str
    config: dict[str, Any]
    result: OptimizationResult | None = None
    result_snapshot: dict[str, Any] | None = None
    error: str | None = None
    progress_current: int = 0
    progress_total: int = 0
    phase: str = ""
    message: str = ""
    live_trials: list[TrialResult] = field(default_factory=list)
    live_trial_snapshots: list[dict[str, Any]] = field(default_factory=list)
    cancel_requested: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class OptimizationSweepStore:
    def __init__(self, persistence: JobPersistence | None = None) -> None:
        self._sweeps: dict[str, OptimizationSweep] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._persistence = persistence if persistence is not None else create_job_persistence()

    def create(self, sweep_id: str, config: dict[str, Any]) -> OptimizationSweep:
        sweep = OptimizationSweep(id=sweep_id, status="pending", config=config)
        self._sweeps[sweep_id] = sweep
        self._persist(sweep)
        return sweep

    def get(self, sweep_id: str) -> OptimizationSweep | None:
        sweep = self._sweeps.get(sweep_id)
        if sweep is not None:
            return sweep
        record = self._persistence.load(NAMESPACE, sweep_id)
        if record is None:
            return None
        hydrated = self._hydrate(record)
        self._sweeps[sweep_id] = hydrated
        if record.get("status") in ACTIVE_STATUSES and hydrated.status == "failed":
            self._persist(hydrated)
        return hydrated

    def update(self, sweep: OptimizationSweep) -> None:
        sweep.updated_at = datetime.now(UTC)
        if sweep.result is not None:
            sweep.result_snapshot = result_to_dict(sweep.result)
        if sweep.live_trials:
            sweep.live_trial_snapshots = [trial_to_dict(t) for t in sweep.live_trials]
        self._sweeps[sweep.id] = sweep
        self._persist(sweep)

    def set_task(self, sweep_id: str, task: asyncio.Task[None]) -> None:
        self._tasks[sweep_id] = task

    def clear_task(self, sweep_id: str) -> None:
        self._tasks.pop(sweep_id, None)

    def has_active(self) -> bool:
        if any(s.status in ACTIVE_STATUSES for s in self._sweeps.values()):
            return True
        return self._persistence.has_active(NAMESPACE)

    def request_cancel(self, sweep_id: str) -> OptimizationSweep | None:
        sweep = self.get(sweep_id)
        if sweep is None:
            return None
        if sweep.status not in ACTIVE_STATUSES:
            return sweep
        sweep.cancel_requested = True
        sweep.message = "Cancel requested…"
        self.update(sweep)
        task = self._tasks.get(sweep_id)
        if task is not None and not task.done():
            task.cancel()
        return sweep

    def clear_local(self) -> None:
        """Drop process-local state (keeps persistence). Used to simulate restart."""
        self._sweeps.clear()
        self._tasks.clear()

    def _persist(self, sweep: OptimizationSweep) -> None:
        self._persistence.save(NAMESPACE, sweep.id, self._serialize(sweep))

    def _serialize(self, sweep: OptimizationSweep) -> dict[str, Any]:
        snapshot = sweep.result_snapshot
        if snapshot is None and sweep.result is not None:
            snapshot = result_to_dict(sweep.result)
        live = sweep.live_trial_snapshots
        if not live and sweep.live_trials:
            live = [trial_to_dict(t) for t in sweep.live_trials]
        return {
            "id": sweep.id,
            "status": sweep.status,
            "config": sweep.config,
            "error": sweep.error,
            "progress_current": sweep.progress_current,
            "progress_total": sweep.progress_total,
            "phase": sweep.phase,
            "message": sweep.message,
            "cancel_requested": sweep.cancel_requested,
            "created_at": sweep.created_at.isoformat(),
            "updated_at": sweep.updated_at.isoformat(),
            "result_snapshot": snapshot,
            "live_trial_snapshots": live,
        }

    def _hydrate(self, record: dict[str, Any]) -> OptimizationSweep:
        status = str(record.get("status", "failed"))
        error = record.get("error")
        message = str(record.get("message") or "")
        # Orphaned in-flight jobs after process death cannot continue.
        if status in ACTIVE_STATUSES:
            status = "failed"
            error = error or "Job interrupted by server restart"
            message = message or "Interrupted by server restart."
        return OptimizationSweep(
            id=str(record["id"]),
            status=status,
            config=dict(record.get("config") or {}),
            result=None,
            result_snapshot=record.get("result_snapshot"),
            error=error,
            progress_current=int(record.get("progress_current") or 0),
            progress_total=int(record.get("progress_total") or 0),
            phase=str(record.get("phase") or ""),
            message=message,
            live_trials=[],
            live_trial_snapshots=list(record.get("live_trial_snapshots") or []),
            cancel_requested=False,
            created_at=_parse_dt(record.get("created_at")),
            updated_at=_parse_dt(record.get("updated_at")),
        )


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return datetime.now(UTC)


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
        "holdout_score": result.holdout_score,
        "holdout_valid": result.holdout_valid,
        "holdout_metrics": (
            {
                "return_pct": result.holdout_outcome.get("return_pct"),
                "total_trades": result.holdout_outcome.get("total_trades"),
                "score": result.holdout_outcome.get("score"),
                "sharpe_ratio": result.holdout_outcome.get("sharpe_ratio"),
                "sortino_ratio": result.holdout_outcome.get("sortino_ratio"),
                "max_drawdown_pct": result.holdout_outcome.get("max_drawdown_pct"),
            }
            if result.holdout_outcome
            else None
        ),
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
    elif sweep.result_snapshot:
        payload.update(sweep.result_snapshot)
    elif sweep.live_trials:
        payload["trials"] = [trial_to_dict(t) for t in sweep.live_trials]
    elif sweep.live_trial_snapshots:
        payload["trials"] = list(sweep.live_trial_snapshots)
    return payload
