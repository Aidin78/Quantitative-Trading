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
    get_indicator_class("macd")().compute(ohlcv, {"fast": 12, "slow": 26, "signal": 9})
    upper = get_indicator_class("bollinger")().compute(
        ohlcv, {"period": 20, "std": 2, "band": "upper"}
    )
    lower = get_indicator_class("bollinger")().compute(
        ohlcv, {"period": 20, "std": 2, "band": "lower"}
    )
    assert 0 <= rsi <= 100
    assert ema > 0
    assert atr > 0
    assert upper > lower


def test_insufficient_data_raises() -> None:
    small = make_sample_ohlcv(bars=5)
    with pytest.raises(InsufficientDataError):
        get_indicator_class("rsi")().compute(small, {"period": 14})
