from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.core.exceptions import InsufficientDataError
from src.features import indicators as _indicators  # noqa: F401 — registers indicator types
from src.features.indicators import _atr_series, _supertrend_components, _supertrend_numpy
from src.features.indicators.base import get_indicator_class
from tests.fixtures.ohlcv import make_sample_ohlcv


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return make_sample_ohlcv(bars=100)


def test_rsi_ema_atr_macd_bollinger_compute(ohlcv: pd.DataFrame) -> None:
    rsi = get_indicator_class("rsi")().compute(ohlcv, {"period": 14})
    ema = get_indicator_class("ema")().compute(ohlcv, {"period": 12})
    atr = get_indicator_class("atr")().compute(ohlcv, {"period": 14})
    macd_params = {"fast": 12, "slow": 26, "signal": 9}
    macd = get_indicator_class("macd")().compute(ohlcv, macd_params)
    macd_signal = get_indicator_class("macd")().compute(
        ohlcv, {**macd_params, "component": "signal"}
    )
    macd_histogram = get_indicator_class("macd")().compute(
        ohlcv, {**macd_params, "component": "histogram"}
    )
    macd_slope = get_indicator_class("macd")().compute(
        ohlcv, {**macd_params, "component": "histogram_slope"}
    )
    upper = get_indicator_class("bollinger")().compute(
        ohlcv, {"period": 20, "std": 2, "band": "upper"}
    )
    lower = get_indicator_class("bollinger")().compute(
        ohlcv, {"period": 20, "std": 2, "band": "lower"}
    )
    middle = get_indicator_class("bollinger")().compute(
        ohlcv, {"period": 20, "std": 2, "band": "middle"}
    )
    assert 0 <= rsi <= 100
    assert ema > 0
    assert atr > 0
    assert macd_histogram == pytest.approx(macd - macd_signal, rel=1e-6, abs=1e-6)
    assert isinstance(macd_slope, float)
    assert upper > lower
    assert lower < middle < upper


def test_adx_components_compute(ohlcv: pd.DataFrame) -> None:
    adx_params = {"period": 14}
    adx = get_indicator_class("adx")().compute(ohlcv, {**adx_params, "component": "adx"})
    plus_di = get_indicator_class("adx")().compute(ohlcv, {**adx_params, "component": "plus_di"})
    minus_di = get_indicator_class("adx")().compute(ohlcv, {**adx_params, "component": "minus_di"})
    assert 0 <= adx <= 100
    assert 0 <= plus_di <= 100
    assert 0 <= minus_di <= 100
    assert plus_di + minus_di > 0


def test_supertrend_compute(ohlcv: pd.DataFrame) -> None:
    st_params = {"period": 10, "multiplier": 3.0}
    line = get_indicator_class("supertrend")().compute(ohlcv, {**st_params, "component": "line"})
    direction = get_indicator_class("supertrend")().compute(
        ohlcv, {**st_params, "component": "direction"}
    )
    close = float(ohlcv["close"].iloc[-1])
    assert line > 0
    assert direction in (-1.0, 1.0)
    if direction > 0:
        assert close >= line
    else:
        assert close <= line


def _reference_supertrend_numpy(
    close: np.ndarray,
    hl2: np.ndarray,
    atr: np.ndarray,
    multiplier: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Frozen pre-extract algorithm for full-series parity checks."""
    n = len(close)
    basic_ub = hl2 + multiplier * atr
    basic_lb = hl2 - multiplier * atr
    final_ub = basic_ub.copy()
    final_lb = basic_lb.copy()

    for i in range(1, n):
        bu = basic_ub[i]
        if bu != bu:
            continue
        prev_ub = final_ub[i - 1]
        if prev_ub == prev_ub and not (bu < prev_ub or close[i - 1] > prev_ub):
            final_ub[i] = prev_ub
        else:
            final_ub[i] = bu

        bl = basic_lb[i]
        prev_lb = final_lb[i - 1]
        if prev_lb == prev_lb and not (bl > prev_lb or close[i - 1] < prev_lb):
            final_lb[i] = prev_lb
        else:
            final_lb[i] = bl

    line = np.full(n, np.nan, dtype=float)
    direction = np.full(n, np.nan, dtype=float)
    in_uptrend = True

    for i in range(n):
        ub = final_ub[i]
        lb = final_lb[i]
        if ub != ub or lb != lb:
            continue

        if i == 0:
            in_uptrend = True
            line[i] = lb
            direction[i] = 1.0
            continue

        if in_uptrend:
            if close[i] < lb:
                in_uptrend = False
                line[i] = ub
                direction[i] = -1.0
            else:
                line[i] = lb
                direction[i] = 1.0
        elif close[i] > ub:
            in_uptrend = True
            line[i] = lb
            direction[i] = 1.0
        else:
            line[i] = ub
            direction[i] = -1.0

    return line, direction


def test_supertrend_full_series_parity_sample(ohlcv: pd.DataFrame) -> None:
    period = 10
    multiplier = 3.0
    close = ohlcv["close"].to_numpy(dtype=np.float64)
    hl2 = ((ohlcv["high"] + ohlcv["low"]) / 2).to_numpy(dtype=np.float64)
    atr = _atr_series(ohlcv, period).to_numpy(dtype=np.float64)

    line, direction = _supertrend_numpy(close, hl2, atr, multiplier)
    ref_line, ref_direction = _reference_supertrend_numpy(close, hl2, atr, multiplier)

    assert np.allclose(line, ref_line, equal_nan=True)
    assert np.array_equal(direction, ref_direction, equal_nan=True)

    wrapped_line, wrapped_direction = _supertrend_components(
        ohlcv, period=period, multiplier=multiplier
    )
    assert np.allclose(wrapped_line.to_numpy(), line, equal_nan=True)
    assert np.array_equal(wrapped_direction.to_numpy(), direction, equal_nan=True)


def test_supertrend_full_series_parity_long_with_warmup() -> None:
    """Longer series exercises ATR NaN warmup + many direction flips."""
    ohlcv = make_sample_ohlcv(bars=500, seed=99)
    period = 14
    multiplier = 2.5
    close = ohlcv["close"].to_numpy(dtype=np.float64)
    hl2 = ((ohlcv["high"] + ohlcv["low"]) / 2).to_numpy(dtype=np.float64)
    atr = _atr_series(ohlcv, period).to_numpy(dtype=np.float64)

    line, direction = _supertrend_numpy(close, hl2, atr, multiplier)
    ref_line, ref_direction = _reference_supertrend_numpy(close, hl2, atr, multiplier)

    assert np.isnan(atr[: period - 1]).all()
    assert np.allclose(line, ref_line, equal_nan=True)
    assert np.array_equal(direction, ref_direction, equal_nan=True)
    assert set(np.unique(direction[~np.isnan(direction)])).issubset({-1.0, 1.0})


def test_supertrend_insufficient_data_raises() -> None:
    small = make_sample_ohlcv(bars=15)
    with pytest.raises(InsufficientDataError, match="supertrend"):
        _supertrend_components(small, period=10, multiplier=3.0)


def test_insufficient_data_raises() -> None:
    small = make_sample_ohlcv(bars=5)
    with pytest.raises(InsufficientDataError):
        get_indicator_class("rsi")().compute(small, {"period": 14})
