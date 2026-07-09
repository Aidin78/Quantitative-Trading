from __future__ import annotations

import pandas as pd
import pytest

from src.core.exceptions import InsufficientDataError
from src.features.indicators import base as _indicators  # noqa: F401
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


def test_insufficient_data_raises() -> None:
    small = make_sample_ohlcv(bars=5)
    with pytest.raises(InsufficientDataError):
        get_indicator_class("rsi")().compute(small, {"period": 14})
