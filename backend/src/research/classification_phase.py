"""Phase 3 — Threshold Classification.

Phase 1 found no direction-prediction edge; Phase 2 found real magnitude
(volatility-clustering) edge. Since magnitude alone carries no side, this
phase does NOT build a standalone LONG/SHORT/NO-TRADE classifier from
direction. Instead it tests the one shape that survives both findings: does
gating an *existing* signal (its own direction, whatever the source) on a
magnitude/volatility threshold change trade quality? This directly produces a
``provider_overrides``-shaped threshold that Phase 4 (the existing
``provider_edge_scorecard``) can validate under real fees/slippage/sizing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.research.signal_evaluator import DEFAULT_HORIZONS

BaseSignal = Callable[[pd.DataFrame], pd.Series]
MagnitudeFilter = Callable[[pd.DataFrame], pd.Series]

#: A gated variant must improve win-rate by at least this many percentage
#: points over the ungated baseline, at the evaluated horizon, to be reported
#: as a Phase-4 candidate.
MIN_WIN_RATE_IMPROVEMENT_PP = 2.0
MIN_TRADES_FOR_COMPARISON = 30


@dataclass(frozen=True)
class ClassificationResult:
    base_signal: str
    filter_name: str
    filter_threshold_percentile: float
    horizon: int
    baseline_trades: int
    baseline_win_rate: float
    filtered_trades: int
    filtered_win_rate: float
    win_rate_improvement_pp: float
    passes_threshold: bool


def _directional_win_rate(
    df_with_targets: pd.DataFrame,
    signal: pd.Series,
    *,
    horizon: int,
    mask: pd.Series | None = None,
) -> tuple[int, float]:
    """A 'trade' is any bar where signal is UP or DOWN; a 'win' is fwd_ret agreeing with it."""
    fwd = df_with_targets[f"fwd_ret_{horizon}"]
    active = signal.isin(["UP", "DOWN"]) & fwd.notna()
    if mask is not None:
        active = active & mask
    if not active.any():
        return 0, float("nan")
    pred_up = (signal == "UP") & active
    pred_down = (signal == "DOWN") & active
    wins = ((pred_up & (fwd > 0)) | (pred_down & (fwd < 0))).sum()
    trades = int(active.sum())
    return trades, (wins / trades * 100) if trades else float("nan")


def evaluate_magnitude_gate(
    df_with_targets: pd.DataFrame,
    *,
    base_signal_name: str,
    base_signal: pd.Series,
    filter_name: str,
    filter_series: pd.Series,
    percentile_threshold: float,
    horizon: int = 14,
) -> ClassificationResult:
    """Compare win-rate of ``base_signal`` unfiltered vs. gated on a magnitude percentile.

    ``filter_series`` is expected to already be a rolling percentile (0-100,
    e.g. from ``magnitude_phase.atr_pct_percentile``); ``percentile_threshold``
    keeps only bars where it's at or above that value (i.e. "volatility is
    currently elevated relative to its own recent history").
    """
    baseline_trades, baseline_win_rate = _directional_win_rate(
        df_with_targets, base_signal, horizon=horizon
    )
    gate_mask = filter_series >= percentile_threshold
    filtered_trades, filtered_win_rate = _directional_win_rate(
        df_with_targets, base_signal, horizon=horizon, mask=gate_mask
    )

    improvement = (
        filtered_win_rate - baseline_win_rate
        if not (np.isnan(filtered_win_rate) or np.isnan(baseline_win_rate))
        else float("nan")
    )
    passes = bool(
        filtered_trades >= MIN_TRADES_FOR_COMPARISON
        and not np.isnan(improvement)
        and improvement >= MIN_WIN_RATE_IMPROVEMENT_PP
    )

    return ClassificationResult(
        base_signal=base_signal_name,
        filter_name=filter_name,
        filter_threshold_percentile=percentile_threshold,
        horizon=horizon,
        baseline_trades=baseline_trades,
        baseline_win_rate=baseline_win_rate,
        filtered_trades=filtered_trades,
        filtered_win_rate=filtered_win_rate,
        win_rate_improvement_pp=improvement,
        passes_threshold=passes,
    )


def run_classification_phase(
    df_with_targets: pd.DataFrame,
    *,
    base_signals: dict[str, BaseSignal],
    magnitude_filters: dict[str, MagnitudeFilter],
    percentile_thresholds: tuple[float, ...] = (50.0, 70.0, 90.0),
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> list[ClassificationResult]:
    results: list[ClassificationResult] = []
    for base_name, base_fn in base_signals.items():
        base_signal = base_fn(df_with_targets)
        for filter_name, filter_fn in magnitude_filters.items():
            filter_series = filter_fn(df_with_targets)
            for threshold in percentile_thresholds:
                for horizon in horizons:
                    results.append(
                        evaluate_magnitude_gate(
                            df_with_targets,
                            base_signal_name=base_name,
                            base_signal=base_signal,
                            filter_name=filter_name,
                            filter_series=filter_series,
                            percentile_threshold=threshold,
                            horizon=horizon,
                        )
                    )
    return results
