from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.validation.optimization_space import OptimizationSpace


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
    holdout_score: float | None = None
    holdout_outcome: dict[str, Any] | None = None
    holdout_valid: bool = False


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
        pareto_eligible = [trial for trial in eligible if trial.pareto_rank == 0]
        pool = pareto_eligible if pareto_eligible else eligible
        return max(pool, key=lambda trial: trial.composite_score or float("-inf"))
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


_AGGREGATE_MEAN_KEYS = (
    "return_pct",
    "win_rate",
    "profit_factor",
    "max_drawdown_pct",
    "max_drawdown",
    "sharpe_ratio",
    "sortino_ratio",
    "trade_sharpe_ratio",
    "score",
    "optimization_score",
)


def _aggregate_fold_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge per-fold outcomes for selection gates (sum trades, mean key scalars)."""
    if not outcomes:
        return {}
    if len(outcomes) == 1:
        return dict(outcomes[0])

    aggregated = dict(outcomes[-1])
    aggregated["total_trades"] = sum(int(o.get("total_trades", 0)) for o in outcomes)
    aggregated["positions_opened"] = sum(int(o.get("positions_opened", 0)) for o in outcomes)
    aggregated["positions_closed"] = sum(int(o.get("positions_closed", 0)) for o in outcomes)
    aggregated["orders_rejected"] = sum(int(o.get("orders_rejected", 0)) for o in outcomes)

    for key in _AGGREGATE_MEAN_KEYS:
        values: list[float] = []
        for outcome in outcomes:
            raw = outcome.get(key)
            if raw is None:
                continue
            try:
                parsed = float(raw)
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                values.append(parsed)
        if values:
            aggregated[key] = sum(values) / len(values)

    # Stability should reflect all folds' months when available.
    months: list[Any] = []
    for outcome in outcomes:
        months.extend(outcome.get("monthly_breakdown") or [])
    if months:
        aggregated["monthly_breakdown"] = months
    return aggregated
