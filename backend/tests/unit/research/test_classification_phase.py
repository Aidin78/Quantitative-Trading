from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.execution.config import load_default_fill_model
from src.research.classification_phase import (
    MIN_TRADES_FOR_COMPARISON,
    MIN_WIN_RATE_IMPROVEMENT_PP,
    _net_of_fees,
    _trade_pnls,
    _trade_stats_from_pnls,
    evaluate_magnitude_gate,
    run_classification_phase,
)
from src.research.direction_phase import ema_compare
from src.research.magnitude_phase import PERCENTILE_PREDICTORS, atr_pct_percentile
from src.research.signal_evaluator import compute_forward_targets
from tests.fixtures.ohlcv import make_sample_ohlcv


@pytest.fixture
def df_with_targets() -> pd.DataFrame:
    df = make_sample_ohlcv(bars=250)
    return compute_forward_targets(df, horizons=(4, 14))


def test_evaluate_magnitude_gate_filtered_trades_never_exceed_baseline(
    df_with_targets: pd.DataFrame,
) -> None:
    base_signal = ema_compare(df_with_targets)
    filter_series = atr_pct_percentile(df_with_targets)
    result = evaluate_magnitude_gate(
        df_with_targets,
        base_signal_name="ema",
        base_signal=base_signal,
        filter_name="atr_pct_percentile_200",
        filter_series=filter_series,
        percentile_threshold=70.0,
        horizon=4,
    )
    assert result.filtered_trades <= result.baseline_trades


def test_evaluate_magnitude_gate_win_rates_are_valid_percentages(
    df_with_targets: pd.DataFrame,
) -> None:
    base_signal = ema_compare(df_with_targets)
    filter_series = atr_pct_percentile(df_with_targets)
    result = evaluate_magnitude_gate(
        df_with_targets,
        base_signal_name="ema",
        base_signal=base_signal,
        filter_name="atr_pct_percentile_200",
        filter_series=filter_series,
        percentile_threshold=50.0,
        horizon=4,
    )
    if result.baseline_trades > 0:
        assert 0.0 <= result.baseline_win_rate <= 100.0
    if result.filtered_trades > 0:
        assert 0.0 <= result.filtered_win_rate <= 100.0


def test_passes_threshold_requires_minimum_trade_count(df_with_targets: pd.DataFrame) -> None:
    """A gate that starves the sample down to near-zero trades must never pass,
    even if the (noisy, tiny-sample) win rate happens to look great.
    """
    base_signal = ema_compare(df_with_targets)
    filter_series = atr_pct_percentile(df_with_targets)
    result = evaluate_magnitude_gate(
        df_with_targets,
        base_signal_name="ema",
        base_signal=base_signal,
        filter_name="atr_pct_percentile_200",
        filter_series=filter_series,
        percentile_threshold=99.9,  # near-empty gate on this small fixture
        horizon=4,
    )
    if result.filtered_trades < MIN_TRADES_FOR_COMPARISON:
        assert result.passes_threshold is False


def test_passes_threshold_requires_minimum_improvement() -> None:
    """A gate that improves win-rate by less than the threshold, even with
    plenty of trades, must not pass — construct a case where filtered and
    baseline win-rate are equal.
    """
    df = make_sample_ohlcv(bars=250)
    df_with_targets = compute_forward_targets(df, horizons=(4,))
    base_signal = ema_compare(df_with_targets)
    # A filter that keeps everything (threshold 0) can't improve win-rate —
    # filtered == baseline exactly.
    always_on = pd.Series(100.0, index=df_with_targets.index)
    result = evaluate_magnitude_gate(
        df_with_targets,
        base_signal_name="ema",
        base_signal=base_signal,
        filter_name="always_on",
        filter_series=always_on,
        percentile_threshold=0.0,
        horizon=4,
    )
    assert result.win_rate_improvement_pp == pytest.approx(0.0, abs=1e-9)
    assert result.passes_threshold is False


def test_run_classification_phase_covers_full_grid(df_with_targets: pd.DataFrame) -> None:
    base_signals = {"ema": ema_compare}
    thresholds = (50.0, 90.0)
    horizons = (4, 14)
    results = run_classification_phase(
        df_with_targets,
        base_signals=base_signals,
        magnitude_filters=PERCENTILE_PREDICTORS,
        percentile_thresholds=thresholds,
        horizons=horizons,
    )
    expected_count = (
        len(base_signals) * len(PERCENTILE_PREDICTORS) * len(thresholds) * len(horizons)
    )
    assert len(results) == expected_count


def test_improvement_threshold_constant_is_positive() -> None:
    assert MIN_WIN_RATE_IMPROVEMENT_PP > 0


def test_trade_pnls_signed_by_direction() -> None:
    """UP predictions take +fwd_ret; DOWN predictions take -fwd_ret."""
    df = pd.DataFrame({"fwd_ret_4": [1.0, -2.0, 3.0, -4.0]})
    signal = pd.Series(["UP", "UP", "DOWN", "DOWN"])
    pnls = _trade_pnls(df, signal, horizon=4)
    assert list(pnls) == [1.0, -2.0, -3.0, 4.0]


def test_trade_pnls_excludes_flat_and_nan() -> None:
    df = pd.DataFrame({"fwd_ret_4": [1.0, 2.0, float("nan"), 4.0]})
    signal = pd.Series(["UP", "FLAT", "UP", "UP"])
    pnls = _trade_pnls(df, signal, horizon=4)
    assert list(pnls) == [1.0, 4.0]


def test_trade_pnls_respects_mask() -> None:
    df = pd.DataFrame({"fwd_ret_4": [1.0, 2.0, 3.0, 4.0]})
    signal = pd.Series(["UP", "UP", "UP", "UP"])
    mask = pd.Series([True, False, True, False])
    pnls = _trade_pnls(df, signal, horizon=4, mask=mask)
    assert list(pnls) == [1.0, 3.0]


def test_trade_stats_from_pnls_known_values() -> None:
    """2 wins (+2, +4), 2 losses (-1, -3): verify each stat by hand."""
    pnls = np.array([2.0, -1.0, 4.0, -3.0])
    stats = _trade_stats_from_pnls(pnls)
    assert stats.trades == 4
    assert stats.win_rate == pytest.approx(50.0)
    assert stats.expectancy == pytest.approx(0.5)  # mean(2,-1,4,-3) = 2/4
    assert stats.profit_factor == pytest.approx(6.0 / 4.0)  # gross_profit/gross_loss
    assert stats.avg_win == pytest.approx(3.0)  # mean(2,4)
    assert stats.avg_loss == pytest.approx(-2.0)  # mean(-1,-3)
    # equity = [2, 1, 5, 2]; peak = [2, 2, 5, 5]; drawdown = [0, 1, 0, 3]
    assert stats.max_drawdown_pct == pytest.approx(3.0)


def test_trade_stats_from_pnls_empty() -> None:
    stats = _trade_stats_from_pnls(np.array([]))
    assert stats.trades == 0
    assert np.isnan(stats.expectancy)


def test_trade_stats_all_wins_profit_factor_is_inf() -> None:
    stats = _trade_stats_from_pnls(np.array([1.0, 2.0, 3.0]))
    assert stats.profit_factor == float("inf")
    assert stats.avg_loss == 0.0


def test_net_of_fees_reduces_expectancy_by_round_trip_cost() -> None:
    fill_model = load_default_fill_model()
    round_trip_cost_pct = 2 * (fill_model.fee_bps + fill_model.slippage_bps) / 100
    pnls = np.array([2.0, -1.0, 4.0, -3.0])
    gross = _trade_stats_from_pnls(pnls)
    net = _net_of_fees(pnls)
    assert net.expectancy == pytest.approx(gross.expectancy - round_trip_cost_pct)
    assert net.trades == gross.trades


def test_evaluate_magnitude_gate_attaches_trade_stats(df_with_targets: pd.DataFrame) -> None:
    base_signal = ema_compare(df_with_targets)
    filter_series = atr_pct_percentile(df_with_targets)
    result = evaluate_magnitude_gate(
        df_with_targets,
        base_signal_name="ema",
        base_signal=base_signal,
        filter_name="atr_pct_percentile_200",
        filter_series=filter_series,
        percentile_threshold=50.0,
        horizon=4,
    )
    assert result.filtered_stats.trades == result.filtered_trades
    assert result.baseline_stats.trades == result.baseline_trades
    # Net-of-fees expectancy must never exceed gross expectancy (costs only subtract).
    if result.filtered_stats.trades > 0:
        assert result.filtered_stats_net_fees.expectancy <= result.filtered_stats.expectancy
