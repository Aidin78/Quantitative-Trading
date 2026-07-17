from __future__ import annotations

import asyncio
import math
import uuid
from datetime import datetime
from typing import Any, Literal

from src.core.settings import get_settings
from src.data.market_cache import get_or_download_csv
from src.validation.harness import ValidationProgressCallback
from src.validation.job_runner import run_validation_job
from src.validation.optimization_progress import (
    ProgressCallback,
    ProgressEvent,
    emit_progress,
)
from src.validation.optimization_scoring import (
    OptimizationResult,
    TrialResult,
    _aggregate_fold_outcomes,
    _trial_test_trades,
    build_selection_message,
    composite_score,
    compute_stability,
    select_best,
)
from src.validation.optimization_space import (
    OptimizationSpace,
    generate_trials,
    generate_trials_optuna,
    refine_trials_around,
)
from src.validation.optimization_windows import split_holdout, split_train_test
from src.validation.trial_config import (
    build_engine_config_from_trial,
    build_execution_config_from_trial,
    build_features_config_from_trial,
    build_provider_overrides,
    synthetic_revision_from_trial,
)
from src.validation.walk_forward import (
    WalkForwardWindow,
    build_anchored_walk_forward_windows,
    build_walk_forward_windows,
)


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
    on_validation_progress: ValidationProgressCallback | None = None,
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
        on_progress=on_validation_progress,
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
    outcomes: list[dict[str, Any]] = []
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
        outcomes.append(outcome)
    mean_score = sum(scores) / len(scores) if scores else 0.0
    if len(scores) > 1:
        variance = sum((score - mean_score) ** 2 for score in scores) / (len(scores) - 1)
        fold_std = math.sqrt(variance)
    else:
        fold_std = 0.0
    return mean_score, _aggregate_fold_outcomes(outcomes), scores, fold_std


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
    walk_forward_mode: Literal["fixed", "anchored"] = "anchored",
    local_refine: bool = True,
    search_method: Literal["grid", "optuna"] = "grid",
    min_trades_holdout: int | None = None,
    max_parallel_trials: int = 1,
    on_progress: ProgressCallback | None = None,
) -> OptimizationResult:
    """Run a parameter sweep.

    Train-phase trials may run concurrently when ``max_parallel_trials`` > 1
    (asyncio semaphore; not ProcessPool). Test/refine/holdout stay sequential.
    Default ``max_parallel_trials=1`` preserves the historical sequential loop.
    """
    opt_space = space or OptimizationSpace()
    (opt_start, opt_end), holdout = split_holdout(start, end, holdout_ratio=holdout_ratio)
    holdout_start, holdout_end = holdout if holdout else (None, None)
    holdout_min_trades = (
        min_trades_holdout if min_trades_holdout is not None else max(1, min_trades // 2)
    )
    parallel = max(1, int(max_parallel_trials))

    effective_source = source
    resolved_csv_path = csv_path
    if source == "exchange" and not csv_path:
        settings = get_settings()
        # Prefetch the full [start, end] range so holdout bars are on disk too.
        resolved_csv_path = str(
            await get_or_download_csv(
                exchange_id=settings.exchange_id,
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
            )
        )
        effective_source = "csv"

    if walk_forward_windows > 1:
        build_windows = (
            build_anchored_walk_forward_windows
            if walk_forward_mode == "anchored"
            else build_walk_forward_windows
        )
        wf_windows = build_windows(
            opt_start, opt_end, windows=walk_forward_windows, train_ratio=train_ratio
        )
    else:
        wf_windows = []
    if wf_windows:
        # Label the full multi-fold span (not just first-train / last-test).
        train_start = wf_windows[0].train_start
        train_end = max(window.train_end for window in wf_windows)
        test_start = min(window.test_start for window in wf_windows)
        test_end = wf_windows[-1].test_end
    else:
        (train_start, train_end), (test_start, test_end) = split_train_test(
            opt_start, opt_end, train_ratio=train_ratio
        )

    trial_params = (
        generate_trials_optuna(opt_space, max_trials=max_trials, seed=seed)
        if search_method == "optuna"
        else generate_trials(opt_space, max_trials=max_trials, seed=seed)
    )
    n_train = len(trial_params)
    n_test = min(top_k, n_train)
    total_steps = n_train + n_test
    if local_refine and n_train > 0:
        total_steps += min(9, n_train)
    step = 0
    train_results: list[TrialResult] = []

    semaphore = asyncio.Semaphore(parallel)
    progress_lock = asyncio.Lock()
    completed_train = 0
    indexed_results: list[TrialResult | None] = [None] * n_train

    async def _train_one(index: int, params: dict[str, Any]) -> TrialResult:
        nonlocal completed_train
        trial_number = index + 1

        async with semaphore:
            async with progress_lock:
                start_step = completed_train

            async def validation_progress(
                event,
                *,
                _trial_number: int = trial_number,
                _start_step: int = start_step,
            ) -> None:
                if on_progress is None or event.phase != "backtest" or event.total <= 0:
                    return
                await emit_progress(
                    on_progress,
                    ProgressEvent(
                        current=_start_step,
                        total=total_steps,
                        phase="train",
                        stage="start",
                        train_count=n_train,
                        test_count=n_test,
                        detail=(
                            f"Training candidate {_trial_number} of {n_train} "
                            f"— bar {event.current}/{event.total}"
                        ),
                    ),
                )

            await emit_progress(
                on_progress,
                ProgressEvent(
                    current=start_step,
                    total=total_steps,
                    phase="train",
                    stage="start",
                    train_count=n_train,
                    test_count=n_test,
                    detail=(
                        f"Training candidate {trial_number} of {n_train} " "on in-sample data…"
                    ),
                ),
            )
            if wf_windows:
                train_score, train_outcome, fold_scores, fold_std = await _score_trial_windows(
                    params=params,
                    symbol=symbol,
                    timeframe=timeframe,
                    windows=wf_windows,
                    source=effective_source,
                    initial_capital=initial_capital,
                    csv_path=resolved_csv_path,
                    segment="train",
                )
                revision_id = synthetic_revision_from_trial(params).revision_id
            else:
                train_score, train_outcome, revision_id = await _run_trial(
                    params=params,
                    symbol=symbol,
                    timeframe=timeframe,
                    start=train_start,
                    end=train_end,
                    source=effective_source,
                    initial_capital=initial_capital,
                    csv_path=resolved_csv_path,
                    on_validation_progress=validation_progress,
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
            async with progress_lock:
                completed_train += 1
                done_step = completed_train
            await emit_progress(
                on_progress,
                ProgressEvent(
                    current=done_step,
                    total=total_steps,
                    phase="train",
                    stage="done",
                    trial=trial,
                    train_count=n_train,
                    test_count=n_test,
                ),
            )
            return trial

    if n_train:
        tasks = [
            asyncio.create_task(_train_one(index, params))
            for index, params in enumerate(trial_params)
        ]
        try:
            results = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        for index, trial in enumerate(results):
            indexed_results[index] = trial
        train_results = [trial for trial in indexed_results if trial is not None]
        step = completed_train
    ranked = sorted(train_results, key=lambda trial: trial.train_score, reverse=True)
    finalists = ranked[: min(top_k, len(ranked))]

    if local_refine and finalists:
        refine_params = refine_trials_around(
            [trial.params for trial in finalists[:3]],
            opt_space,
            max_refine=min(9, max_trials),
        )
        for params in refine_params:
            await emit_progress(
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
                    source=effective_source,
                    initial_capital=initial_capital,
                    csv_path=resolved_csv_path,
                    segment="train",
                )
                revision_id = synthetic_revision_from_trial(params).revision_id
            else:
                train_score, train_outcome, revision_id = await _run_trial(
                    params=params,
                    symbol=symbol,
                    timeframe=timeframe,
                    start=train_start,
                    end=train_end,
                    source=effective_source,
                    initial_capital=initial_capital,
                    csv_path=resolved_csv_path,
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
            await emit_progress(
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
        await emit_progress(
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
                source=effective_source,
                initial_capital=initial_capital,
                csv_path=resolved_csv_path,
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
                source=effective_source,
                initial_capital=initial_capital,
                csv_path=resolved_csv_path,
            )
        trial.test_score = test_score
        trial.test_outcome = test_outcome
        trial.stability = compute_stability(test_outcome)
        trial.composite_score = composite_score(
            trial,
            min_trades=min_trades,
            min_return_pct=min_return_pct,
        )
        step += 1
        await emit_progress(
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

    holdout_score: float | None = None
    holdout_outcome: dict[str, Any] | None = None
    holdout_valid = False
    if best is not None and holdout_start is not None and holdout_end is not None:
        holdout_score, holdout_outcome, _ = await _run_trial(
            params=best.params,
            symbol=symbol,
            timeframe=timeframe,
            start=holdout_start,
            end=holdout_end,
            source=effective_source,
            initial_capital=initial_capital,
            csv_path=resolved_csv_path,
        )
        h_trades = int(holdout_outcome.get("total_trades", 0))
        h_return = float(holdout_outcome.get("return_pct", 0))
        holdout_valid = h_trades >= holdout_min_trades and h_return >= min_return_pct
        if best_valid and not holdout_valid:
            # Keep `best` for inspection, but mark apply-invalid and expose fallback.
            best_valid = False
            holdout_msg = (
                f"Holdout check failed: {h_trades} trades, {h_return:.2f}% return "
                f"(need >={holdout_min_trades} trades and >={min_return_pct}% return). "
                "Pass use_fallback=true to apply the closest candidate."
            )
            selection_message = (
                f"{selection_message} {holdout_msg}".strip() if selection_message else holdout_msg
            )
            if fallback_trial is None and finalists:
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
        holdout_score=holdout_score,
        holdout_outcome=holdout_outcome,
        holdout_valid=holdout_valid,
    )
