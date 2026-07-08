from __future__ import annotations

import itertools
import random
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from src.api.services.validation_runner import run_validation_job
from src.validation.trial_config import (
    build_engine_config_from_trial,
    build_execution_config_from_trial,
    build_provider_overrides,
    synthetic_revision_from_trial,
)


@dataclass(frozen=True)
class OptimizationSpace:
    min_confidence: tuple[float, ...] = (0.6, 0.65, 0.7)
    min_risk_reward: tuple[float, ...] = (1.2, 1.5, 2.0)
    min_agreeing_providers: tuple[int, ...] = (1, 2)
    sl_atr_mult: tuple[float, ...] = (1.0, 1.5, 2.0)
    tp_atr_mult: tuple[float, ...] = (2.0, 3.0, 4.0)
    max_bars_in_trade: tuple[int, ...] = (24, 48, 96)

    def as_dict(self) -> dict[str, tuple[Any, ...]]:
        return {
            "min_confidence": self.min_confidence,
            "min_risk_reward": self.min_risk_reward,
            "min_agreeing_providers": self.min_agreeing_providers,
            "sl_atr_mult": self.sl_atr_mult,
            "tp_atr_mult": self.tp_atr_mult,
            "max_bars_in_trade": self.max_bars_in_trade,
        }

    @classmethod
    def from_dict(cls, data: dict[str, list[Any]] | None) -> OptimizationSpace:
        if not data:
            return cls()
        fields: dict[str, tuple[Any, ...]] = {}
        defaults = cls()
        for key, default_val in defaults.as_dict().items():
            if key in data:
                fields[key] = tuple(data[key])
            else:
                fields[key] = default_val
        return cls(**fields)


@dataclass
class TrialResult:
    trial_id: str
    params: dict[str, Any]
    train_score: float
    train_outcome: dict[str, Any]
    test_score: float | None = None
    test_outcome: dict[str, Any] | None = None
    stability: float | None = None
    revision_id: str | None = None


@dataclass
class OptimizationResult:
    sweep_id: str
    symbol: str
    timeframe: str
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    trials: list[TrialResult] = field(default_factory=list)
    best: TrialResult | None = None
    space: OptimizationSpace = field(default_factory=OptimizationSpace)


def split_train_test(
    start: datetime,
    end: datetime,
    *,
    train_ratio: float,
) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    total = end - start
    if total <= timedelta(0):
        raise ValueError("end must be after start")
    train_end = start + timedelta(seconds=total.total_seconds() * train_ratio)
    return (start, train_end), (train_end, end)


def generate_trials(
    space: OptimizationSpace,
    *,
    max_trials: int = 40,
    seed: int = 42,
) -> list[dict[str, Any]]:
    keys = [
        "min_confidence",
        "min_risk_reward",
        "min_agreeing_providers",
        "sl_atr_mult",
        "tp_atr_mult",
        "max_bars_in_trade",
    ]
    values = [space.as_dict()[k] for k in keys]
    all_combos = [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*values)]
    if len(all_combos) <= max_trials:
        return all_combos
    rng = random.Random(seed)
    return rng.sample(all_combos, max_trials)


def compute_stability(outcome: dict[str, Any]) -> float:
    months = outcome.get("monthly_breakdown") or []
    if not months:
        return 0.0
    positive = sum(1 for month in months if float(month.get("pnl", 0)) > 0)
    return positive / len(months)


async def _run_trial(
    *,
    params: dict[str, Any],
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    source: Literal["exchange", "csv"],
    initial_capital: float,
    csv_path: str | None,
) -> tuple[float, dict[str, Any], str]:
    revision = synthetic_revision_from_trial(params)
    result = await run_validation_job(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start.date().isoformat(),
        end_date=end.date().isoformat(),
        csv_path=csv_path,
        source=source,
        initial_capital=initial_capital,
        persist_db=False,
        revision_id=revision.revision_id,
        engine_config=build_engine_config_from_trial(params),
        provider_overrides=build_provider_overrides(params),
        execution_config=build_execution_config_from_trial(params),
    )
    outcome = result.outcome_metrics or {}
    return float(outcome.get("score", 0)), outcome, revision.revision_id


@dataclass
class ProgressEvent:
    current: int
    total: int
    phase: Literal["train", "test"]
    stage: Literal["start", "done"]
    trial: TrialResult | None = None
    train_count: int = 0
    test_count: int = 0


ProgressCallback = Callable[[ProgressEvent], Awaitable[None] | None]


async def _emit(
    on_progress: ProgressCallback | None,
    event: ProgressEvent,
) -> None:
    if on_progress is None:
        return
    maybe = on_progress(event)
    if maybe is not None:
        await maybe


async def run_optimization(
    *,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    source: Literal["exchange", "csv"] = "csv",
    initial_capital: float = 10000.0,
    train_ratio: float = 0.7,
    max_trials: int = 40,
    top_k: int = 5,
    space: OptimizationSpace | None = None,
    csv_path: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> OptimizationResult:
    opt_space = space or OptimizationSpace()
    (train_start, train_end), (test_start, test_end) = split_train_test(
        start, end, train_ratio=train_ratio
    )
    trial_params = generate_trials(opt_space, max_trials=max_trials)
    n_train = len(trial_params)
    n_test = min(top_k, n_train)
    total_steps = n_train + n_test
    step = 0
    train_results: list[TrialResult] = []

    for params in trial_params:
        await _emit(
            on_progress,
            ProgressEvent(
                current=step,
                total=total_steps,
                phase="train",
                stage="start",
                train_count=n_train,
                test_count=n_test,
            ),
        )
        train_score, train_outcome, revision_id = await _run_trial(
            params=params,
            symbol=symbol,
            timeframe=timeframe,
            start=train_start,
            end=train_end,
            source=source,
            initial_capital=initial_capital,
            csv_path=csv_path,
        )
        trial = TrialResult(
            trial_id=f"trial_{uuid.uuid4().hex[:8]}",
            params=params,
            train_score=train_score,
            train_outcome=train_outcome,
            revision_id=revision_id,
        )
        train_results.append(trial)
        step += 1
        await _emit(
            on_progress,
            ProgressEvent(
                current=step,
                total=total_steps,
                phase="train",
                stage="done",
                trial=trial,
                train_count=n_train,
                test_count=n_test,
            ),
        )

    ranked = sorted(train_results, key=lambda t: t.train_score, reverse=True)
    finalists = ranked[: min(top_k, len(ranked))]

    for trial in finalists:
        await _emit(
            on_progress,
            ProgressEvent(
                current=step,
                total=total_steps,
                phase="test",
                stage="start",
                trial=trial,
                train_count=n_train,
                test_count=n_test,
            ),
        )
        test_score, test_outcome, _ = await _run_trial(
            params=trial.params,
            symbol=symbol,
            timeframe=timeframe,
            start=test_start,
            end=test_end,
            source=source,
            initial_capital=initial_capital,
            csv_path=csv_path,
        )
        trial.test_score = test_score
        trial.test_outcome = test_outcome
        trial.stability = compute_stability(test_outcome)
        step += 1
        await _emit(
            on_progress,
            ProgressEvent(
                current=step,
                total=total_steps,
                phase="test",
                stage="done",
                trial=trial,
                train_count=n_train,
                test_count=n_test,
            ),
        )

    best = (
        max(
            finalists,
            key=lambda t: (t.test_score if t.test_score is not None else float("-inf")),
        )
        if finalists
        else None
    )

    return OptimizationResult(
        sweep_id=f"sweep_{uuid.uuid4().hex[:12]}",
        symbol=symbol,
        timeframe=timeframe,
        train_start=train_start,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
        trials=train_results,
        best=best,
        space=opt_space,
    )
