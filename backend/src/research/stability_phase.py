"""Phase 3b — Candidate stability: sub-window repeatability, regime concentration,
percentile-threshold sweep, and ATR-based volatility filter/sizing overlays.

This module never touches the Decision Engine, a provider, or execution — it
stays inside the statistical research pipeline (see ``classification_phase``'s
module docstring) and answers one question before any of this is ever ported
into a real provider: does a Phase-3 magnitude-gated candidate's apparent edge
survive being sliced into sub-windows and regimes, or is it a single-window
artifact?
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.research.classification_phase import (
    MIN_TRADES_FOR_COMPARISON,
    BaseSignal,
    MagnitudeFilter,
    TradeStats,
    _net_of_fees,
    _trade_pnls,
    _trade_stats_from_pnls,
)
from src.research.direction_phase import ema_compare
from src.research.magnitude_phase import atr_pct

#: A single regime bucket accounting for more than this share of a
#: sub-window's filtered trades is flagged as concentration risk — mirrors
#: ``governance.candidate_evaluator.MAX_SINGLE_REGIME_SHARE``.
MAX_SINGLE_REGIME_SHARE = 0.8

#: Same rationale as candidate_evaluator.MIN_TRADES_FOR_REGIME_CHECK: below
#: this, regime concentration is indistinguishable from noise.
MIN_TRADES_FOR_REGIME_CHECK = 20

#: Reuses config/features.yaml's context.trend / context.volatility defaults
#: (ema_compare fast=12/slow=26; atr_pct low=0.3/high=1.0) so regime labels
#: here match what ContextDeriver would label the same bar in a live/backtest
#: run — kept as local constants (not read from YAML) because this module
#: works on a raw OHLCV DataFrame, not a live FeatureSet/MarketContext.
TREND_EMA_FAST = 12
TREND_EMA_SLOW = 26
VOLATILITY_ATR_LOW = 0.3
VOLATILITY_ATR_HIGH = 1.0


def regime_label(df: pd.DataFrame) -> pd.Series:
    """Per-bar ``{UP,DOWN,SIDEWAYS}_{LOW,NORMAL,HIGH}`` label.

    Mirrors ``ContextDeriver._derive_trend``/``_derive_volatility`` exactly
    (same EMA compare, same ATR% thresholds) so a bar's label here matches
    what the live/backtest ``MarketContext.trend``/``.volatility`` would say
    for that bar — without depending on ContextDeriver's live wiring.
    """
    ema_fast = df["close"].ewm(span=TREND_EMA_FAST, adjust=False).mean()
    ema_slow = df["close"].ewm(span=TREND_EMA_SLOW, adjust=False).mean()
    trend = pd.Series(
        np.select(
            [ema_fast > ema_slow, ema_fast < ema_slow],
            ["UP", "DOWN"],
            default="SIDEWAYS",
        ),
        index=df.index,
    )
    atr_pct_series = atr_pct(df)
    volatility = pd.Series(
        np.select(
            [atr_pct_series < VOLATILITY_ATR_LOW, atr_pct_series > VOLATILITY_ATR_HIGH],
            ["LOW", "HIGH"],
            default="NORMAL",
        ),
        index=df.index,
    )
    return trend + "_" + volatility


def split_into_sub_windows(df: pd.DataFrame, *, n_windows: int) -> list[pd.DataFrame]:
    """Split a DataFrame into ``n_windows`` contiguous, equal-size, non-overlapping slices.

    Row-count based (not date based) since this module works on a raw OHLCV
    DataFrame, not a ``ValidationConfig`` date range — mirrors the equal-share
    philosophy of ``validation.optimization_windows.split_train_test`` without
    depending on it (that module builds live validation configs).
    """
    if n_windows < 1:
        raise ValueError("n_windows must be >= 1")
    n = len(df)
    edges = np.linspace(0, n, n_windows + 1, dtype=int)
    return [df.iloc[edges[i] : edges[i + 1]] for i in range(n_windows)]


@dataclass(frozen=True)
class SubWindowResult:
    window_index: int
    n_windows: int
    baseline_stats: TradeStats
    filtered_stats: TradeStats
    filtered_stats_net_fees: TradeStats
    win_rate_improvement_pp: float
    regime_trade_counts: dict[str, int] = field(default_factory=dict)
    regime_concentration_share: float = 0.0
    regime_concentration_flag: bool = False


def _regime_breakdown(
    df_window: pd.DataFrame, *, active_mask: np.ndarray
) -> tuple[dict[str, int], float, bool]:
    labels = regime_label(df_window).to_numpy()[active_mask]
    if labels.size == 0:
        return {}, 0.0, False
    counts = pd.Series(labels).value_counts()
    total = int(counts.sum())
    max_share = float(counts.iloc[0] / total) if total else 0.0
    flagged = total >= MIN_TRADES_FOR_REGIME_CHECK and max_share > MAX_SINGLE_REGIME_SHARE
    return {str(k): int(v) for k, v in counts.items()}, max_share, flagged


def evaluate_candidate_stability(
    df_with_targets: pd.DataFrame,
    *,
    base_signal: BaseSignal = ema_compare,
    magnitude_filter: MagnitudeFilter,
    percentile_threshold: float,
    horizon: int,
    n_windows: int = 3,
) -> list[SubWindowResult]:
    """Re-run one fixed (base_signal, filter, threshold, horizon) candidate on
    each of ``n_windows`` contiguous sub-windows of ``df_with_targets``.

    Deliberately re-derives the base signal and filter series independently
    per sub-window (not sliced from a full-range computation) so each
    window's rolling indicators (e.g. the 200-bar percentile rank) only see
    their own history — the same "no information from outside this slice"
    discipline walk-forward folds require elsewhere in this platform.
    """
    windows = split_into_sub_windows(df_with_targets, n_windows=n_windows)
    results: list[SubWindowResult] = []
    for index, window_df in enumerate(windows):
        if len(window_df) == 0:
            continue
        signal = base_signal(window_df)
        filter_series = magnitude_filter(window_df)
        gate_mask = (filter_series >= percentile_threshold).to_numpy()

        baseline_pnls = _trade_pnls(window_df, signal, horizon=horizon)
        filtered_pnls = _trade_pnls(
            window_df, signal, horizon=horizon, mask=filter_series >= percentile_threshold
        )

        fwd = window_df[f"fwd_ret_{horizon}"]
        active = (signal.isin(["UP", "DOWN"]) & fwd.notna() & gate_mask).to_numpy()
        regime_counts, max_share, flagged = _regime_breakdown(window_df, active_mask=active)

        baseline_stats = _trade_stats_from_pnls(baseline_pnls)
        filtered_stats = _trade_stats_from_pnls(filtered_pnls)
        improvement = (
            filtered_stats.win_rate - baseline_stats.win_rate
            if not (np.isnan(filtered_stats.win_rate) or np.isnan(baseline_stats.win_rate))
            else float("nan")
        )

        results.append(
            SubWindowResult(
                window_index=index,
                n_windows=n_windows,
                baseline_stats=baseline_stats,
                filtered_stats=filtered_stats,
                filtered_stats_net_fees=_net_of_fees(filtered_pnls),
                win_rate_improvement_pp=improvement,
                regime_trade_counts=regime_counts,
                regime_concentration_share=max_share,
                regime_concentration_flag=flagged,
            )
        )
    return results


@dataclass(frozen=True)
class StabilityVerdict:
    n_sub_windows: int
    n_windows_improved: int
    n_windows_min_improvement_met: int
    passes_repeatability: bool
    any_regime_concentration_flag: bool
    detail: str


#: A candidate is only called "repeatable" if the win-rate improvement holds
#: (stays positive and above this floor) in at least this fraction of
#: sub-windows — looser than MIN_WIN_RATE_IMPROVEMENT_PP (2.0pp) itself since
#: sub-windows have fewer trades each and more noise than the full range.
MIN_SUB_WINDOW_IMPROVEMENT_PP = 1.0
MIN_REPEATABILITY_FRACTION = 2 / 3


def summarize_stability(results: list[SubWindowResult]) -> StabilityVerdict:
    n = len(results)
    improved = sum(1 for r in results if r.win_rate_improvement_pp > 0)
    met_floor = sum(
        1
        for r in results
        if not np.isnan(r.win_rate_improvement_pp)
        and r.win_rate_improvement_pp >= MIN_SUB_WINDOW_IMPROVEMENT_PP
    )
    any_flag = any(r.regime_concentration_flag for r in results)
    passes = n > 0 and (met_floor / n) >= MIN_REPEATABILITY_FRACTION and not any_flag
    detail = (
        f"{met_floor}/{n} sub-windows met the >= {MIN_SUB_WINDOW_IMPROVEMENT_PP:.1f}pp floor "
        f"({improved}/{n} were directionally positive at all)"
        + ("; regime concentration flagged in >=1 window" if any_flag else "")
    )
    return StabilityVerdict(
        n_sub_windows=n,
        n_windows_improved=improved,
        n_windows_min_improvement_met=met_floor,
        passes_repeatability=passes,
        any_regime_concentration_flag=any_flag,
        detail=detail,
    )


@dataclass(frozen=True)
class PercentileSweepPoint:
    percentile_threshold: float
    train_stats: list[SubWindowResult]
    holdout_stats: SubWindowResult | None


@dataclass(frozen=True)
class PercentileSweepResult:
    points: list[PercentileSweepPoint]
    best_threshold_on_train: float | None
    best_threshold_rank_unstable: bool
    holdout_verdict_for_best: str


def sweep_percentile_thresholds(
    df_with_targets: pd.DataFrame,
    *,
    base_signal: BaseSignal = ema_compare,
    magnitude_filter: MagnitudeFilter,
    horizon: int,
    percentile_thresholds: tuple[float, ...] = (75.0, 80.0, 85.0, 90.0, 95.0),
    n_windows: int = 3,
) -> PercentileSweepResult:
    """Sweep a magnitude-gate threshold as a hyperparameter, with a held-out
    final sub-window never used for threshold selection.

    Despite the name, this works for any scalar threshold compared against
    ``magnitude_filter``'s output via ``>=`` — a rank-percentile filter (0-100,
    e.g. ``atr_pct_percentile``) or a fixed absolute-scale filter (e.g. raw
    ``atr_pct``, single-digit %) are both valid; only the values passed in
    ``percentile_thresholds`` need to match the filter's scale.

    Selecting "the best threshold" by trying several and keeping the winner
    is exactly a multiple-comparisons setup — the more thresholds tried, the
    likelier one looks good by chance alone. Two guards: (1) the last
    sub-window is a holdout, touched only after a threshold is already
    chosen from the earlier ones; (2) ``best_threshold_rank_unstable`` flags
    when the top threshold's *rank* (not just its score) is not consistent
    across the train sub-windows — a threshold that wins train-window 1 but
    loses in train-window 2 is a signature of noise, not edge.
    """
    if n_windows < 2:
        raise ValueError("n_windows must be >= 2 to reserve a holdout sub-window")

    points: list[PercentileSweepPoint] = []
    for threshold in percentile_thresholds:
        all_windows = evaluate_candidate_stability(
            df_with_targets,
            base_signal=base_signal,
            magnitude_filter=magnitude_filter,
            percentile_threshold=threshold,
            horizon=horizon,
            n_windows=n_windows,
        )
        train_windows = [r for r in all_windows if r.window_index < n_windows - 1]
        holdout_windows = [r for r in all_windows if r.window_index == n_windows - 1]
        points.append(
            PercentileSweepPoint(
                percentile_threshold=threshold,
                train_stats=train_windows,
                holdout_stats=holdout_windows[0] if holdout_windows else None,
            )
        )

    def _train_score(point: PercentileSweepPoint) -> float:
        valid = [
            r.win_rate_improvement_pp
            for r in point.train_stats
            if not np.isnan(r.win_rate_improvement_pp)
            and r.filtered_stats.trades >= MIN_TRADES_FOR_COMPARISON
        ]
        return float(np.mean(valid)) if valid else float("-inf")

    scored = [(p, _train_score(p)) for p in points]
    eligible = [(p, s) for p, s in scored if s > float("-inf")]
    if not eligible:
        return PercentileSweepResult(
            points=points,
            best_threshold_on_train=None,
            best_threshold_rank_unstable=True,
            holdout_verdict_for_best="not_evaluated: no threshold had enough train trades",
        )

    best_point, _ = max(eligible, key=lambda pair: pair[1])
    best_threshold = best_point.percentile_threshold

    # Rank stability: does the best-on-average threshold also win in each
    # individual train sub-window, not just on average across them?
    per_window_ranks: list[bool] = []
    n_train_windows = n_windows - 1
    for window_idx in range(n_train_windows):
        window_scores = [
            (
                p.percentile_threshold,
                next(
                    (
                        r.win_rate_improvement_pp
                        for r in p.train_stats
                        if r.window_index == window_idx and not np.isnan(r.win_rate_improvement_pp)
                    ),
                    float("-inf"),
                ),
            )
            for p in points
        ]
        if all(score == float("-inf") for _, score in window_scores):
            continue
        winner = max(window_scores, key=lambda pair: pair[1])[0]
        per_window_ranks.append(winner == best_threshold)
    rank_unstable = len(per_window_ranks) > 0 and not all(per_window_ranks)

    holdout = best_point.holdout_stats
    if holdout is None or holdout.filtered_stats.trades < MIN_TRADES_FOR_COMPARISON:
        holdout_verdict = "not_evaluated: holdout sub-window has too few trades"
    elif np.isnan(holdout.win_rate_improvement_pp):
        holdout_verdict = "not_evaluated: holdout win-rate improvement undefined"
    elif holdout.win_rate_improvement_pp >= MIN_SUB_WINDOW_IMPROVEMENT_PP:
        holdout_verdict = f"confirmed: holdout improvement {holdout.win_rate_improvement_pp:+.1f}pp"
    else:
        holdout_verdict = (
            f"failed: holdout improvement only {holdout.win_rate_improvement_pp:+.1f}pp"
        )

    return PercentileSweepResult(
        points=points,
        best_threshold_on_train=best_threshold,
        best_threshold_rank_unstable=rank_unstable,
        holdout_verdict_for_best=holdout_verdict,
    )


# --- ATR-based volatility filtering / sizing overlays -----------------------


def apply_min_atr_filter(
    df_window: pd.DataFrame,
    *,
    gate_mask: pd.Series,
    min_atr_pct: float = VOLATILITY_ATR_LOW,
) -> pd.Series:
    """AND the existing percentile gate with an absolute minimum-volatility
    filter — mirrors the live platform's ``market_filter.py`` rejection on
    ``context.atr_pct < config.min_atr_pct`` (same default threshold as
    ``config/features.yaml``'s ``volatility.low``), applied here as a second,
    independent gate rather than replacing the percentile-rank gate.
    """
    absolute_atr = atr_pct(df_window)
    return gate_mask & (absolute_atr >= min_atr_pct)


def size_multiplier_from_percentile(atr_percentile: pd.Series) -> pd.Series:
    """Inverse-volatility weight: shrink size as the ATR percentile rises.

    A simple linear map clipped to [0.5, 1.5] — halves size at the top of the
    observed volatility range, 1.5x at the bottom. This is a pre-screening
    approximation of volatility-scaled sizing, not the platform's real
    risk-based sizing (``execution.simulated_pricing.position_size``, which
    sizes off the actual ATR-derived stop-loss distance) — the real sizing
    interacts with stop distance in a way this weight does not capture.
    """
    return (1.5 - atr_percentile / 100).clip(lower=0.5, upper=1.5)


def evaluate_volatility_overlay(
    df_window: pd.DataFrame,
    *,
    base_signal: BaseSignal,
    magnitude_filter: MagnitudeFilter,
    percentile_threshold: float,
    horizon: int,
    min_atr_pct: float = VOLATILITY_ATR_LOW,
) -> dict[str, TradeStats]:
    """Compare the candidate's trade stats under three variants: the gate
    alone, the gate plus an absolute min-ATR filter, and the gate with
    volatility-scaled (simulated) position sizing.
    """
    signal = base_signal(df_window)
    filter_series = magnitude_filter(df_window)
    gate_mask = filter_series >= percentile_threshold

    gate_only_pnls = _trade_pnls(df_window, signal, horizon=horizon, mask=gate_mask)

    filtered_mask = apply_min_atr_filter(df_window, gate_mask=gate_mask, min_atr_pct=min_atr_pct)
    with_atr_filter_pnls = _trade_pnls(df_window, signal, horizon=horizon, mask=filtered_mask)

    fwd = df_window[f"fwd_ret_{horizon}"]
    active = signal.isin(["UP", "DOWN"]) & fwd.notna() & gate_mask
    atr_percentile_at_entry = filter_series[active.to_numpy()]
    direction = np.where(signal[active.to_numpy()] == "UP", 1.0, -1.0)
    raw_pnls = fwd[active.to_numpy()].to_numpy() * direction
    weights = size_multiplier_from_percentile(atr_percentile_at_entry).to_numpy()
    sized_pnls = raw_pnls * weights

    return {
        "gate_only": _trade_stats_from_pnls(gate_only_pnls),
        "gate_plus_min_atr_filter": _trade_stats_from_pnls(with_atr_filter_pnls),
        "gate_plus_volatility_sizing": _trade_stats_from_pnls(sized_pnls),
    }
