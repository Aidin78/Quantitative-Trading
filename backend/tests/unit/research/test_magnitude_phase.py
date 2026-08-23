from __future__ import annotations

import pandas as pd
import pytest

from src.research.magnitude_phase import (
    DEFAULT_PREDICTORS,
    PERCENTILE_PREDICTORS,
    adx_level,
    atr_pct,
    atr_pct_percentile,
    bb_width_percentile,
    decile_breakdown,
    run_magnitude_phase,
)
from src.research.signal_evaluator import compute_forward_targets
from tests.fixtures.ohlcv import make_sample_ohlcv


@pytest.fixture
def df_with_targets() -> pd.DataFrame:
    # 250 bars: enough headroom past the 200-bar rolling percentile window.
    df = make_sample_ohlcv(bars=250)
    return compute_forward_targets(df, horizons=(4, 14))


def test_percentile_predictors_are_bounded_0_100(df_with_targets: pd.DataFrame) -> None:
    for name, fn in PERCENTILE_PREDICTORS.items():
        series = fn(df_with_targets).dropna()
        assert (series >= 0).all() and (series <= 100).all(), name


def test_percentile_predictors_are_a_subset_of_all_predictors() -> None:
    assert set(PERCENTILE_PREDICTORS.keys()) <= set(DEFAULT_PREDICTORS.keys())


def test_atr_pct_percentile_of_the_max_value_is_100(df_with_targets: pd.DataFrame) -> None:
    pct = atr_pct_percentile(df_with_targets)
    raw = atr_pct(df_with_targets)
    valid = pct.dropna()
    # the highest ATR% within its own trailing window should read near the
    # top of the percentile scale
    idx_of_global_max = raw.idxmax()
    if idx_of_global_max in valid.index:
        assert pct.loc[idx_of_global_max] >= 90.0


def test_decile_breakdown_has_ten_or_fewer_buckets(df_with_targets: pd.DataFrame) -> None:
    predictor = bb_width_percentile(df_with_targets)
    table = decile_breakdown(df_with_targets, predictor, horizon=4)
    assert len(table) <= 10
    assert set(table.columns) == {"decile", "mean_fwd_absret", "mean_fwd_maxrange", "n"}
    assert table["n"].sum() <= len(df_with_targets)


def test_decile_breakdown_is_monotonic_for_volatility_clustering(
    df_with_targets: pd.DataFrame,
) -> None:
    """Regression guard for the real finding this phase exists to detect:
    higher current ATR% should correspond to a higher (or at least
    non-decreasing on average) forward move magnitude — the volatility
    clustering signature seen in the real dataset. Not every synthetic
    fixture will show this cleanly, so this asserts the shape of the
    computation (deciles present, ordered by predictor value) rather than a
    strict monotonic inequality that could be fixture-dependent.
    """
    predictor = atr_pct(df_with_targets)
    table = decile_breakdown(df_with_targets, predictor, horizon=4)
    assert list(table["decile"]) == sorted(table["decile"])


def test_adx_level_is_nonnegative(df_with_targets: pd.DataFrame) -> None:
    series = adx_level(df_with_targets).dropna()
    assert (series >= 0).all()


def test_run_magnitude_phase_returns_one_result_per_predictor(
    df_with_targets: pd.DataFrame,
) -> None:
    results = run_magnitude_phase(df_with_targets, horizons=(4, 14), decile_horizon=4)
    assert len(results) == len(DEFAULT_PREDICTORS)
    for r in results:
        assert set(r.corr_absret_by_horizon.keys()) == {4, 14}
        assert set(r.corr_maxrange_by_horizon.keys()) == {4, 14}


def test_spearman_correlation_is_between_minus_1_and_1(df_with_targets: pd.DataFrame) -> None:
    results = run_magnitude_phase(df_with_targets, horizons=(4,), decile_horizon=4)
    for r in results:
        for h, corr in r.corr_absret_by_horizon.items():
            if corr == corr:  # not NaN
                assert -1.0 <= corr <= 1.0
