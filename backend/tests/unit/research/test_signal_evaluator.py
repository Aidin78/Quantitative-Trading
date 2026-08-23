from __future__ import annotations

import pandas as pd
import pytest

from src.research.signal_evaluator import compute_forward_targets
from tests.fixtures.ohlcv import make_sample_ohlcv


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    return make_sample_ohlcv(bars=60)


def test_forward_return_uses_shift_negative_h(ohlcv_df: pd.DataFrame) -> None:
    out = compute_forward_targets(ohlcv_df, horizons=(4,))
    close = ohlcv_df["close"]
    expected = (close.shift(-4) / close - 1) * 100
    pd.testing.assert_series_equal(out["fwd_ret_4"], expected, check_names=False)


def test_forward_absret_is_abs_of_forward_ret(ohlcv_df: pd.DataFrame) -> None:
    out = compute_forward_targets(ohlcv_df, horizons=(4,))
    pd.testing.assert_series_equal(out["fwd_absret_4"], out["fwd_ret_4"].abs(), check_names=False)


def test_forward_targets_are_nan_at_the_tail(ohlcv_df: pd.DataFrame) -> None:
    """The last `h` bars have no future data — they must be NaN, never filled."""
    out = compute_forward_targets(ohlcv_df, horizons=(4,))
    assert out["fwd_ret_4"].iloc[-4:].isna().all()
    assert out["fwd_maxrange_4"].iloc[-4:].isna().all()


def test_forward_target_at_bar_t_is_independent_of_bars_before_t(ohlcv_df: pd.DataFrame) -> None:
    """Regression guard for the look-ahead bug found in this exact research: a
    forward target computed for bar t must be identical whether or not the
    rows before t are present, since it is derived purely from t and bars
    after t. A metric that (even accidentally) depended on a full run's
    history looking backward would fail this.
    """
    full = compute_forward_targets(ohlcv_df, horizons=(4,))
    truncated_input = ohlcv_df.iloc[20:].reset_index(drop=True)
    truncated = compute_forward_targets(truncated_input, horizons=(4,))

    # bar 25 in `full` corresponds to bar 5 in `truncated` (offset by the 20 dropped rows)
    full_value = full["fwd_ret_4"].iloc[25]
    truncated_value = truncated["fwd_ret_4"].iloc[5]
    assert full_value == pytest.approx(truncated_value)


def test_forward_maxrange_uses_only_future_high_low(ohlcv_df: pd.DataFrame) -> None:
    """fwd_maxrange_h at bar t must equal the range of bars (t+1 .. t+h] only —
    never include bar t's own high/low (that would leak the "current" bar into
    a target meant to represent only what happens next).
    """
    out = compute_forward_targets(ohlcv_df, horizons=(4,))
    t = 10
    window = ohlcv_df.iloc[t + 1 : t + 1 + 4]
    expected_range = (window["high"].max() - window["low"].min()) / ohlcv_df["close"].iloc[t] * 100
    assert out["fwd_maxrange_4"].iloc[t] == pytest.approx(expected_range)


def test_multiple_horizons_each_get_their_own_columns(ohlcv_df: pd.DataFrame) -> None:
    out = compute_forward_targets(ohlcv_df, horizons=(4, 8))
    for h in (4, 8):
        assert f"fwd_ret_{h}" in out.columns
        assert f"fwd_absret_{h}" in out.columns
        assert f"fwd_maxrange_{h}" in out.columns
    # different horizons must diverge (not just copies of each other)
    assert not out["fwd_ret_4"].equals(out["fwd_ret_8"])


def test_compute_forward_targets_does_not_mutate_input(ohlcv_df: pd.DataFrame) -> None:
    original_columns = list(ohlcv_df.columns)
    compute_forward_targets(ohlcv_df, horizons=(4,))
    assert list(ohlcv_df.columns) == original_columns
