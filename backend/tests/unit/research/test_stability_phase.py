from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.research.direction_phase import ema_compare
from src.research.magnitude_phase import atr_pct_percentile
from src.research.signal_evaluator import compute_forward_targets
from src.research.stability_phase import (
    MAX_SINGLE_REGIME_SHARE,
    MIN_SUB_WINDOW_IMPROVEMENT_PP,
    apply_min_atr_filter,
    evaluate_candidate_stability,
    evaluate_threshold_band,
    evaluate_volatility_overlay,
    regime_label,
    size_multiplier_from_percentile,
    split_into_sub_windows,
    summarize_stability,
    sweep_percentile_thresholds,
)
from tests.fixtures.ohlcv import make_sample_ohlcv


@pytest.fixture
def df_with_targets() -> pd.DataFrame:
    df = make_sample_ohlcv(bars=900)
    return compute_forward_targets(df, horizons=(4, 14))


def test_split_into_sub_windows_covers_all_rows_without_overlap(
    df_with_targets: pd.DataFrame,
) -> None:
    windows = split_into_sub_windows(df_with_targets, n_windows=3)
    assert len(windows) == 3
    total = sum(len(w) for w in windows)
    assert total == len(df_with_targets)
    # Contiguous: window i's last index precedes window i+1's first index.
    for i in range(len(windows) - 1):
        assert windows[i].index[-1] < windows[i + 1].index[0]


def test_split_into_sub_windows_rejects_invalid_count(df_with_targets: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        split_into_sub_windows(df_with_targets, n_windows=0)


def test_regime_label_shape_matches_trend_x_volatility(df_with_targets: pd.DataFrame) -> None:
    labels = regime_label(df_with_targets)
    allowed_trends = {"UP", "DOWN", "SIDEWAYS"}
    allowed_vols = {"LOW", "NORMAL", "HIGH"}
    for label in labels.dropna().unique():
        trend, _, vol = label.partition("_")
        assert trend in allowed_trends
        assert vol in allowed_vols


def test_evaluate_candidate_stability_returns_one_result_per_window(
    df_with_targets: pd.DataFrame,
) -> None:
    results = evaluate_candidate_stability(
        df_with_targets,
        base_signal=ema_compare,
        magnitude_filter=atr_pct_percentile,
        percentile_threshold=70.0,
        horizon=4,
        n_windows=3,
    )
    assert len(results) == 3
    assert [r.window_index for r in results] == [0, 1, 2]


def test_summarize_stability_requires_majority_of_windows_above_floor() -> None:
    from src.research.classification_phase import _EMPTY_TRADE_STATS
    from src.research.stability_phase import SubWindowResult

    good = SubWindowResult(
        window_index=0,
        n_windows=3,
        baseline_stats=_EMPTY_TRADE_STATS,
        filtered_stats=_EMPTY_TRADE_STATS,
        filtered_stats_net_fees=_EMPTY_TRADE_STATS,
        win_rate_improvement_pp=MIN_SUB_WINDOW_IMPROVEMENT_PP + 1.0,
    )
    bad = SubWindowResult(
        window_index=1,
        n_windows=3,
        baseline_stats=_EMPTY_TRADE_STATS,
        filtered_stats=_EMPTY_TRADE_STATS,
        filtered_stats_net_fees=_EMPTY_TRADE_STATS,
        win_rate_improvement_pp=-1.0,
    )
    # 1/2 good windows is below MIN_REPEATABILITY_FRACTION (2/3) -> fails.
    verdict = summarize_stability([good, bad])
    assert verdict.passes_repeatability is False

    # 2/2 good windows passes.
    verdict_all_good = summarize_stability([good, good])
    assert verdict_all_good.passes_repeatability is True


def test_summarize_stability_flags_regime_concentration() -> None:
    from src.research.classification_phase import _EMPTY_TRADE_STATS
    from src.research.stability_phase import SubWindowResult

    concentrated = SubWindowResult(
        window_index=0,
        n_windows=1,
        baseline_stats=_EMPTY_TRADE_STATS,
        filtered_stats=_EMPTY_TRADE_STATS,
        filtered_stats_net_fees=_EMPTY_TRADE_STATS,
        win_rate_improvement_pp=5.0,
        regime_trade_counts={"UP_HIGH": 100, "DOWN_LOW": 1},
        regime_concentration_share=0.99,
        regime_concentration_flag=True,
    )
    verdict = summarize_stability([concentrated])
    assert verdict.any_regime_concentration_flag is True
    assert verdict.passes_repeatability is False


def test_sweep_percentile_thresholds_reserves_last_window_as_holdout(
    df_with_targets: pd.DataFrame,
) -> None:
    result = sweep_percentile_thresholds(
        df_with_targets,
        base_signal=ema_compare,
        magnitude_filter=atr_pct_percentile,
        horizon=4,
        percentile_thresholds=(50.0, 70.0, 90.0),
        n_windows=3,
    )
    assert len(result.points) == 3
    for point in result.points:
        # train_stats never contains the last window index (n_windows - 1).
        assert all(r.window_index < 2 for r in point.train_stats)
        if point.holdout_stats is not None:
            assert point.holdout_stats.window_index == 2


def test_sweep_percentile_thresholds_requires_at_least_two_windows(
    df_with_targets: pd.DataFrame,
) -> None:
    with pytest.raises(ValueError):
        sweep_percentile_thresholds(
            df_with_targets,
            magnitude_filter=atr_pct_percentile,
            horizon=4,
            n_windows=1,
        )


def test_apply_min_atr_filter_only_narrows_the_mask(df_with_targets: pd.DataFrame) -> None:
    filter_series = atr_pct_percentile(df_with_targets)
    gate_mask = filter_series >= 70.0
    narrowed = apply_min_atr_filter(df_with_targets, gate_mask=gate_mask, min_atr_pct=0.3)
    assert (narrowed & ~gate_mask).sum() == 0  # never turns on a bar the gate rejected


def test_size_multiplier_is_clipped_and_inverse_to_percentile() -> None:
    percentiles = pd.Series([0.0, 50.0, 100.0])
    weights = size_multiplier_from_percentile(percentiles)
    assert weights.iloc[0] == pytest.approx(1.5)  # low vol -> largest size
    assert weights.iloc[2] == pytest.approx(0.5)  # high vol -> smallest size
    assert weights.is_monotonic_decreasing


def test_evaluate_volatility_overlay_returns_three_variants(
    df_with_targets: pd.DataFrame,
) -> None:
    overlay = evaluate_volatility_overlay(
        df_with_targets,
        base_signal=ema_compare,
        magnitude_filter=atr_pct_percentile,
        percentile_threshold=70.0,
        horizon=4,
    )
    assert set(overlay.keys()) == {
        "gate_only",
        "gate_plus_min_atr_filter",
        "gate_plus_volatility_sizing",
    }
    # min-ATR filter can only keep the same or fewer trades than gate alone.
    assert overlay["gate_plus_min_atr_filter"].trades <= overlay["gate_only"].trades
    # Sizing overlay changes weights, not trade count.
    assert overlay["gate_plus_volatility_sizing"].trades == overlay["gate_only"].trades


def test_evaluate_threshold_band_scores_every_threshold_on_every_window(
    df_with_targets: pd.DataFrame,
) -> None:
    result = evaluate_threshold_band(
        df_with_targets,
        base_signal=ema_compare,
        magnitude_filter=atr_pct_percentile,
        horizon=4,
        percentile_thresholds=(85.0, 90.0, 95.0),
        n_windows=3,
    )
    # No holdout reservation: every (threshold, window) pair is scored.
    assert len(result.rows) == 3 * 3
    seen = {(r.percentile_threshold, r.window_index) for r in result.rows}
    assert seen == {(t, w) for t in (85.0, 90.0, 95.0) for w in range(3)}
    assert result.windows_evaluated <= result.n_windows
    assert result.windows_all_positive_across_band <= result.windows_evaluated


def test_evaluate_threshold_band_excludes_windows_with_too_few_trades(
    df_with_targets: pd.DataFrame,
) -> None:
    # A very high threshold on a small sample starves at least one window of
    # MIN_TRADES_FOR_COMPARISON trades; that window must be excluded from
    # windows_evaluated rather than counted as a band failure.
    result = evaluate_threshold_band(
        df_with_targets,
        base_signal=ema_compare,
        magnitude_filter=atr_pct_percentile,
        horizon=4,
        percentile_thresholds=(85.0, 99.0),
        n_windows=5,
    )
    n_below_min = sum(1 for r in result.rows if r.below_min_trades)
    assert n_below_min > 0  # sanity: this scenario does starve some windows
    assert result.windows_evaluated < result.n_windows
    assert result.windows_evaluated == result.n_windows - len(
        {r.window_index for r in result.rows if r.below_min_trades}
    )


def test_evaluate_threshold_band_is_consistent_only_when_all_windows_positive(
    df_with_targets: pd.DataFrame,
) -> None:
    result = evaluate_threshold_band(
        df_with_targets,
        base_signal=ema_compare,
        magnitude_filter=atr_pct_percentile,
        horizon=4,
        percentile_thresholds=(85.0, 90.0),
        n_windows=3,
    )
    expected = (
        result.windows_evaluated > 0
        and result.windows_all_positive_across_band == result.windows_evaluated
    )
    assert result.band_is_consistent == expected


def test_constants_are_reasonable() -> None:
    assert 0 < MAX_SINGLE_REGIME_SHARE < 1
    assert np.isfinite(MIN_SUB_WINDOW_IMPROVEMENT_PP)
