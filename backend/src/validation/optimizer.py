from __future__ import annotations

import itertools
import math
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
    build_features_config_from_trial,
    build_provider_overrides,
    synthetic_revision_from_trial,
)
from src.validation.walk_forward import WalkForwardWindow, build_walk_forward_windows

TRIAL_PARAM_KEYS = [
    "min_confidence",
    "min_risk_reward",
    "min_agreeing_providers",
    "sl_atr_mult",
    "tp_atr_mult",
    "max_bars_in_trade",
    "oversold",
    "overbought",
    "risk_pct_per_trade",
    "min_atr_pct",
    "session_preset",
    "max_signals_per_day",
    "ema_fast",
    "ema_slow",
    "rsi_period",
    "ema_weight",
    "rsi_weight",
    "ema_enabled",
    "rsi_enabled",
]


@dataclass(frozen=True)
class OptimizationSpace:
    min_confidence: tuple[float, ...] = (0.6, 0.65, 0.7, 0.78)
    min_risk_reward: tuple[float, ...] = (1.0, 1.2, 1.5, 2.0)
    min_agreeing_providers: tuple[int, ...] = (1, 2)
    sl_atr_mult: tuple[float, ...] = (1.0, 1.5, 2.0)
    tp_atr_mult: tuple[float, ...] = (2.0, 3.0, 4.0)
    max_bars_in_trade: tuple[int, ...] = (12, 24, 48)
    oversold: tuple[float, ...] = (25.0, 30.0, 35.0)
    overbought: tuple[float, ...] = (65.0, 70.0, 75.0)
    risk_pct_per_trade: tuple[float, ...] = (0.5, 1.0, 1.5)
    min_atr_pct: tuple[float, ...] = (0.1, 0.3, 0.5)
    session_preset: tuple[str, ...] = ("eu_us", "all")
    max_signals_per_day: tuple[int, ...] = (5, 10, 20)
    ema_fast: tuple[int, ...] = (12,)
    ema_slow: tuple[int, ...] = (26,)
    rsi_period: tuple[int, ...] = (14,)
    ema_weight: tuple[float, ...] = (1.0,)
    rsi_weight: tuple[float, ...] = (1.0,)
    ema_enabled: tuple[int, ...] = (1,)
    rsi_enabled: tuple[int, ...] = (1,)

    def as_dict(self) -> dict[str, tuple[Any, ...]]:
        return {key: getattr(self, key) for key in TRIAL_PARAM_KEYS}

    @classmethod
    def from_dict(cls, data: dict[str, list[Any]] | None) -> OptimizationSpace:
        if not data:
            return cls()
        fields: dict[str, tuple[Any, ...]] = {}
        defaults = cls()
        for key in TRIAL_PARAM_KEYS:
            if key in data:
                fields[key] = tuple(data[key])
            else:
                fields[key] = getattr(defaults, key)
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
    composite_score: float | None = None
    fold_scores: list[float] = field(default_factory=list)
    fold_std: float | None = None
    pareto_rank: int | None = None


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
    best_valid: bool = False
    selection_message: str | None = None
    fallback_trial: TrialResult | None = None
    space: OptimizationSpace = field(default_factory=OptimizationSpace)
    holdout_start: datetime | None = None
    holdout_end: datetime | None = None
    optimization_end: datetime | None = None


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


def split_holdout(
    start: datetime,
    end: datetime,
    *,
    holdout_ratio: float,
) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime] | None]:
    if holdout_ratio <= 0:
        return (start, end), None
    if not 0 < holdout_ratio < 1:
        raise ValueError("holdout_ratio must be between 0 and 1")
    total = end - start
    if total <= timedelta(0):
        raise ValueError("end must be after start")
    opt_end = start + timedelta(seconds=total.total_seconds() * (1 - holdout_ratio))
    return (start, opt_end), (opt_end, end)


def generate_trials(
    space: OptimizationSpace,
    *,
    max_trials: int = 40,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    values = [space.as_dict()[key] for key in TRIAL_PARAM_KEYS]
    all_combos = [
        dict(zip(TRIAL_PARAM_KEYS, combo, strict=True)) for combo in itertools.product(*values)
    ]
    if len(all_combos) <= max_trials:
        return all_combos

    rng = random.Random(seed if seed is not None else random.randrange(2**31))
    stride = max(1, len(all_combos) // max_trials)
    picked: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    for index in range(0, len(all_combos), stride):
        combo = all_combos[index]
        key = tuple(sorted(combo.items()))
        if key not in seen:
            seen.add(key)
            picked.append(combo)
        if len(picked) >= max_trials:
            break

    remaining = [combo for combo in all_combos if tuple(sorted(combo.items())) not in seen]
    while len(picked) < max_trials and remaining:
        choice = rng.choice(remaining)
        key = tuple(sorted(choice.items()))
        if key in seen:
            remaining.remove(choice)
            continue
        seen.add(key)
        picked.append(choice)
        remaining.remove(choice)
    return picked


def refine_trials_around(
    top_trials: list[dict[str, Any]],
    space: OptimizationSpace,
    *,
    max_refine: int = 9,
) -> list[dict[str, Any]]:
    refine_keys = ("sl_atr_mult", "tp_atr_mult", "oversold", "overbought", "min_atr_pct")
    space_map = space.as_dict()
    refined: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()

    for params in top_trials:
        base_key = tuple(sorted(params.items()))
        seen.add(base_key)
        for key in refine_keys:
            values = list(space_map[key])
            if key not in params or len(values) < 2:
                continue
            current = params[key]
            try:
                idx = values.index(current)
            except ValueError:
                continue
            for neighbor_idx in (idx - 1, idx + 1):
                if 0 <= neighbor_idx < len(values):
                    candidate = dict(params)
                    candidate[key] = values[neighbor_idx]
                    candidate_key = tuple(sorted(candidate.items()))
                    if candidate_key not in seen:
                        seen.add(candidate_key)
                        refined.append(candidate)
                        if len(refined) >= max_refine:
                            return refined
    return refined


def compute_stability(outcome: dict[str, Any]) -> float:
    months = outcome.get("monthly_breakdown") or []
    if not months:
        return 0.0
    positive = sum(1 for month in months if float(month.get("pnl", 0)) > 0)
    return positive / len(months)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def composite_score(
    trial: TrialResult,
    *,
    min_trades: int = 20,
    min_return_pct: float = 0.0,
) -> float:
    if trial.test_outcome is None:
        return float("-inf")
    trades = int(trial.test_outcome.get("total_trades", 0))
    return_pct = float(trial.test_outcome.get("return_pct", 0))
    if trades < min_trades or return_pct < min_return_pct:
        return float("-inf")
    test_score = trial.test_score if trial.test_score is not None else float("-inf")
    stability = trial.stability or 0.0
    return_term = _clamp(return_pct / 10.0, -1.0, 1.0) * 100.0
    fold_penalty = (trial.fold_std or 0.0) * 10.0
    return 0.6 * test_score + 0.25 * stability * 100.0 + 0.15 * return_term - fold_penalty


def assign_pareto_ranks(finalists: list[TrialResult]) -> None:
    if not finalists:
        return
    metrics: list[tuple[TrialResult, tuple[float, float, float]]] = []
    for trial in finalists:
        if trial.test_outcome is None:
            continue
        metrics.append(
            (
                trial,
                (
                    float(trial.test_outcome.get("return_pct", 0)),
                    -float(trial.test_outcome.get("max_drawdown_pct", 0)),
                    float(trial.test_outcome.get("profit_factor", 0))
                    if trial.test_outcome.get("profit_factor") != float("inf")
                    else 10.0,
                ),
            )
        )
    for index, (trial, values) in enumerate(metrics):
        dominated = False
        for other_index, (_, other_values) in enumerate(metrics):
            if index == other_index:
                continue
            if all(
                other >= current for other, current in zip(other_values, values, strict=True)
            ) and any(other > current for other, current in zip(other_values, values, strict=True)):
                dominated = True
                break
        trial.pareto_rank = 0 if not dominated else 1


def select_best(
    finalists: list[TrialResult],
    *,
    min_trades: int,
    min_return_pct: float,
) -> TrialResult | None:
    if not finalists:
        return None
    for trial in finalists:
        trial.composite_score = composite_score(
            trial,
            min_trades=min_trades,
            min_return_pct=min_return_pct,
        )
    assign_pareto_ranks(finalists)
    eligible = [
        trial
        for trial in finalists
        if trial.composite_score is not None and trial.composite_score > float("-inf")
    ]
    if eligible:
        return max(eligible, key=lambda trial: trial.composite_score or float("-inf"))
    return None


def _trial_test_trades(trial: TrialResult) -> int:
    if trial.test_outcome is None:
        return 0
    return int(trial.test_outcome.get("total_trades", 0))


def build_selection_message(
    *,
    finalists: list[TrialResult],
    min_trades: int,
    min_return_pct: float,
) -> str:
    if not finalists:
        return "No finalists were evaluated on test data."
    max_trades = max(_trial_test_trades(trial) for trial in finalists)
    agreeing_two = sum(
        1 for trial in finalists if int(trial.params.get("min_agreeing_providers", 1)) >= 2
    )
    hints: list[str] = [
        f"No trial reached {min_trades} test trades (max seen: {max_trades}).",
    ]
    if min_return_pct > 0:
        hints.append(f"Minimum return filter: {min_return_pct}%.")
    if agreeing_two:
        hints.append(
            f"{agreeing_two} finalist(s) require 2 agreeing providers — "
            "EMA and RSI must agree on the same side, which often yields zero trades."
        )
    hints.append(
        "Try: min_agreeing_providers=1, session_preset=all, longer date range, "
        "or WF windows=1 for shorter histories."
    )
    return " ".join(hints)


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
    features_config = build_features_config_from_trial(params)
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
        features_config=features_config,
    )
    outcome = result.outcome_metrics or {}
    score = float(outcome.get("optimization_score", outcome.get("score", 0)))
    return score, outcome, revision.revision_id


async def _score_trial_windows(
    *,
    params: dict[str, Any],
    symbol: str,
    timeframe: str,
    windows: list[WalkForwardWindow],
    source: Literal["exchange", "csv"],
    initial_capital: float,
    csv_path: str | None,
    segment: Literal["train", "test"],
) -> tuple[float, dict[str, Any], list[float], float]:
    scores: list[float] = []
    last_outcome: dict[str, Any] = {}
    for window in windows:
        if segment == "train":
            start, end = window.train_start, window.train_end
        else:
            start, end = window.test_start, window.test_end
        score, outcome, _ = await _run_trial(
            params=params,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            source=source,
            initial_capital=initial_capital,
            csv_path=csv_path,
        )
        scores.append(score)
        last_outcome = outcome
    mean_score = sum(scores) / len(scores) if scores else 0.0
    if len(scores) > 1:
        variance = sum((score - mean_score) ** 2 for score in scores) / (len(scores) - 1)
        fold_std = math.sqrt(variance)
    else:
        fold_std = 0.0
    return mean_score, last_outcome, scores, fold_std


@dataclass
class ProgressEvent:
    current: int
    total: int
    phase: Literal["train", "test", "refine"]
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
    seed: int | None = None,
    min_trades: int = 20,
    min_return_pct: float = 0.0,
    holdout_ratio: float = 0.2,
    walk_forward_windows: int = 1,
    local_refine: bool = True,
    on_progress: ProgressCallback | None = None,
) -> OptimizationResult:
    opt_space = space or OptimizationSpace()
    (opt_start, opt_end), holdout = split_holdout(start, end, holdout_ratio=holdout_ratio)
    holdout_start, holdout_end = holdout if holdout else (None, None)

    wf_windows = (
        build_walk_forward_windows(
            opt_start, opt_end, windows=walk_forward_windows, train_ratio=train_ratio
        )
        if walk_forward_windows > 1
        else []
    )
    if wf_windows:
        train_start, train_end = wf_windows[0].train_start, wf_windows[0].train_end
        test_start, test_end = wf_windows[-1].test_start, wf_windows[-1].test_end
    else:
        (train_start, train_end), (test_start, test_end) = split_train_test(
            opt_start, opt_end, train_ratio=train_ratio
        )

    trial_params = generate_trials(opt_space, max_trials=max_trials, seed=seed)
    n_train = len(trial_params)
    n_test = min(top_k, n_train)
    total_steps = n_train + n_test
    if local_refine and n_train > 0:
        total_steps += min(9, n_train)
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
        if wf_windows:
            train_score, train_outcome, fold_scores, fold_std = await _score_trial_windows(
                params=params,
                symbol=symbol,
                timeframe=timeframe,
                windows=wf_windows,
                source=source,
                initial_capital=initial_capital,
                csv_path=csv_path,
                segment="test",
            )
            revision_id = synthetic_revision_from_trial(params).revision_id
        else:
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
            fold_scores = []
            fold_std = None
        trial = TrialResult(
            trial_id=f"trial_{uuid.uuid4().hex[:8]}",
            params=params,
            train_score=train_score,
            train_outcome=train_outcome,
            revision_id=revision_id,
            fold_scores=fold_scores,
            fold_std=fold_std,
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

    ranked = sorted(train_results, key=lambda trial: trial.train_score, reverse=True)
    finalists = ranked[: min(top_k, len(ranked))]

    if local_refine and finalists:
        refine_params = refine_trials_around(
            [trial.params for trial in finalists[:3]],
            opt_space,
            max_refine=min(9, max_trials),
        )
        for params in refine_params:
            await _emit(
                on_progress,
                ProgressEvent(
                    current=step,
                    total=total_steps,
                    phase="refine",
                    stage="start",
                    train_count=n_train,
                    test_count=n_test,
                ),
            )
            fold_scores: list[float] = []
            fold_std: float | None = None
            if wf_windows:
                train_score, train_outcome, fold_scores, fold_std = await _score_trial_windows(
                    params=params,
                    symbol=symbol,
                    timeframe=timeframe,
                    windows=wf_windows,
                    source=source,
                    initial_capital=initial_capital,
                    csv_path=csv_path,
                    segment="test",
                )
                revision_id = synthetic_revision_from_trial(params).revision_id
            else:
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
                fold_scores = []
                fold_std = None
            trial = TrialResult(
                trial_id=f"trial_{uuid.uuid4().hex[:8]}",
                params=params,
                train_score=train_score,
                train_outcome=train_outcome,
                revision_id=revision_id,
                fold_scores=fold_scores,
                fold_std=fold_std,
            )
            train_results.append(trial)
            finalists.append(trial)
            step += 1
            await _emit(
                on_progress,
                ProgressEvent(
                    current=step,
                    total=total_steps,
                    phase="refine",
                    stage="done",
                    trial=trial,
                    train_count=n_train,
                    test_count=n_test,
                ),
            )
        finalists = sorted(finalists, key=lambda trial: trial.train_score, reverse=True)[:top_k]

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
                test_count=len(finalists),
            ),
        )
        if wf_windows:
            test_score, test_outcome, fold_scores, fold_std = await _score_trial_windows(
                params=trial.params,
                symbol=symbol,
                timeframe=timeframe,
                windows=wf_windows,
                source=source,
                initial_capital=initial_capital,
                csv_path=csv_path,
                segment="test",
            )
            trial.fold_scores = fold_scores
            trial.fold_std = fold_std
        else:
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
                test_count=len(finalists),
            ),
        )

    best = select_best(finalists, min_trades=min_trades, min_return_pct=min_return_pct)
    best_valid = best is not None
    fallback_trial: TrialResult | None = None
    selection_message: str | None = None
    if not best_valid and finalists:
        selection_message = build_selection_message(
            finalists=finalists,
            min_trades=min_trades,
            min_return_pct=min_return_pct,
        )
        fallback_trial = max(finalists, key=_trial_test_trades)

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
        best_valid=best_valid,
        selection_message=selection_message,
        fallback_trial=fallback_trial,
        space=opt_space,
        holdout_start=holdout_start,
        holdout_end=holdout_end,
        optimization_end=opt_end,
    )
