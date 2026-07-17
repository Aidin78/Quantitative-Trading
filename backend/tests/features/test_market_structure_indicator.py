from __future__ import annotations

import pandas as pd
import pytest

from src.core.exceptions import InsufficientDataError
from src.features import indicators as _indicators  # noqa: F401 — registers indicator types
from src.features.indicators.base import get_indicator_class


def _make_uptrend_df(bars: int = 60, *, pivot_bars: int = 3) -> pd.DataFrame:
    """Synthetic HH/HL structure with a final bullish BOS."""
    rows: list[dict[str, float]] = []
    base = 100.0
    for i in range(bars):
        drift = i * 0.4
        wave = 2.0 * ((i % 8) - 4)
        o = base + drift + wave
        c = o + 0.5
        h = max(o, c) + 1.0
        low = min(o, c) - 1.0
        rows.append({"open": o, "high": h, "low": low, "close": c, "volume": 1000.0})
    df = pd.DataFrame(rows)
    # Force a clear break above prior swing high on the last bar.
    df.loc[df.index[-1], "close"] = float(df["high"].max()) + 5.0
    df.loc[df.index[-1], "high"] = float(df.loc[df.index[-1], "close"]) + 1.0
    return df


def _make_downtrend_df(bars: int = 60) -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    base = 200.0
    for i in range(bars):
        drift = -i * 0.4
        wave = 2.0 * ((i % 8) - 4)
        o = base + drift + wave
        c = o - 0.5
        h = max(o, c) + 1.0
        low = min(o, c) - 1.0
        rows.append({"open": o, "high": h, "low": low, "close": c, "volume": 1000.0})
    df = pd.DataFrame(rows)
    df.loc[df.index[-1], "close"] = float(df["low"].min()) - 5.0
    df.loc[df.index[-1], "low"] = float(df.loc[df.index[-1], "close"]) - 1.0
    return df


def test_market_structure_bias_and_bos_compute() -> None:
    params = {"pivot_bars": 3}
    bullish = _make_uptrend_df()
    bias = get_indicator_class("market_structure")().compute(
        bullish, {**params, "component": "bias"}
    )
    bos = get_indicator_class("market_structure")().compute(bullish, {**params, "component": "bos"})
    assert bias in (-1.0, 0.0, 1.0)
    assert bos in (-1.0, 0.0, 1.0)

    bearish = _make_downtrend_df()
    bear_bias = get_indicator_class("market_structure")().compute(
        bearish, {**params, "component": "bias"}
    )
    bear_bos = get_indicator_class("market_structure")().compute(
        bearish, {**params, "component": "bos"}
    )
    assert bear_bias in (-1.0, 0.0, 1.0)
    assert bear_bos in (-1.0, 0.0, 1.0)


def test_market_structure_bullish_bos_on_breakout() -> None:
    df = _make_uptrend_df()
    bos = get_indicator_class("market_structure")().compute(
        df, {"pivot_bars": 3, "component": "bos"}
    )
    assert bos == 1.0


def test_market_structure_bearish_bos_on_breakdown() -> None:
    df = _make_downtrend_df()
    bos = get_indicator_class("market_structure")().compute(
        df, {"pivot_bars": 3, "component": "bos"}
    )
    assert bos == -1.0


def test_market_structure_insufficient_data_raises() -> None:
    small = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0],
            "high": [2.0, 3.0, 4.0],
            "low": [0.5, 1.5, 2.5],
            "close": [1.5, 2.5, 3.5],
            "volume": [100.0, 100.0, 100.0],
        }
    )
    with pytest.raises(InsufficientDataError):
        get_indicator_class("market_structure")().compute(
            small, {"pivot_bars": 5, "component": "bias"}
        )
