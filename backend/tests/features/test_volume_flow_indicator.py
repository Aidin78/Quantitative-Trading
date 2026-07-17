from __future__ import annotations

import pandas as pd
import pytest

from src.core.exceptions import InsufficientDataError
from src.features import indicators as _indicators  # noqa: F401 — registers indicator types
from src.features.indicators.base import get_indicator_class
from tests.fixtures.ohlcv import make_sample_ohlcv


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return make_sample_ohlcv(bars=100)


def test_volume_flow_cmf_and_ratio_compute(ohlcv: pd.DataFrame) -> None:
    params = {"period": 20}
    cmf = get_indicator_class("volume_flow")().compute(ohlcv, {**params, "component": "cmf"})
    ratio = get_indicator_class("volume_flow")().compute(
        ohlcv, {**params, "component": "volume_ratio"}
    )
    assert -1.0 <= cmf <= 1.0
    assert ratio > 0


def test_volume_flow_close_delta(ohlcv: pd.DataFrame) -> None:
    delta = get_indicator_class("volume_flow")().compute(ohlcv, {"component": "close_delta"})
    expected = float(ohlcv["close"].iloc[-1] - ohlcv["close"].iloc[-2])
    assert delta == pytest.approx(expected)


def test_volume_flow_flat_bar_mf_mult_zero(ohlcv: pd.DataFrame) -> None:
    flat = ohlcv.copy()
    flat.loc[flat.index[-1], "high"] = flat.loc[flat.index[-1], "low"]
    cmf = get_indicator_class("volume_flow")().compute(flat, {"period": 20, "component": "cmf"})
    assert isinstance(cmf, float)


def test_volume_flow_insufficient_data_raises() -> None:
    small = make_sample_ohlcv(bars=10)
    with pytest.raises(InsufficientDataError):
        get_indicator_class("volume_flow")().compute(small, {"period": 20, "component": "cmf"})
