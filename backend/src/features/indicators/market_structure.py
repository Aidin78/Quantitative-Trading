from __future__ import annotations

from typing import Any

import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators.base import register_indicator


def _find_confirmed_pivots(
    df: pd.DataFrame,
    *,
    pivot_bars: int,
    up_to_index: int,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    high_series = df["high"]
    low_series = df["low"]
    last_confirmable = up_to_index - pivot_bars
    for i in range(pivot_bars, last_confirmable + 1):
        window_start = i - pivot_bars
        window_end = i + pivot_bars + 1
        window_high = high_series.iloc[window_start:window_end]
        window_low = low_series.iloc[window_start:window_end]
        if float(high_series.iloc[i]) >= float(window_high.max()):
            highs.append((i, float(high_series.iloc[i])))
        if float(low_series.iloc[i]) <= float(window_low.min()):
            lows.append((i, float(low_series.iloc[i])))
    return highs, lows


def _structure_bias(highs: list[tuple[int, float]], lows: list[tuple[int, float]]) -> float:
    if len(highs) < 2 or len(lows) < 2:
        return 0.0
    _, h1 = highs[-2]
    _, h2 = highs[-1]
    _, l1 = lows[-2]
    _, l2 = lows[-1]
    if h2 > h1 and l2 > l1:
        return 1.0
    if h2 < h1 and l2 < l1:
        return -1.0
    return 0.0


def _structure_bos(
    close: float,
    highs: list[tuple[int, float]],
    lows: list[tuple[int, float]],
) -> float:
    if not highs and not lows:
        return 0.0
    if highs and close > highs[-1][1]:
        return 1.0
    if lows and close < lows[-1][1]:
        return -1.0
    return 0.0


def _market_structure_latest(
    df: pd.DataFrame,
    *,
    pivot_bars: int,
) -> tuple[float, float]:
    min_bars = 4 * pivot_bars + 1
    if len(df) < min_bars:
        raise InsufficientDataError(
            f"Insufficient data for market_structure: need at least {min_bars} bars"
        )
    t = len(df) - 1
    highs, lows = _find_confirmed_pivots(df, pivot_bars=pivot_bars, up_to_index=t)
    bias = _structure_bias(highs, lows)
    bos = _structure_bos(float(df["close"].iloc[t]), highs, lows)
    return bias, bos


@register_indicator("market_structure")
class MarketStructureIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        pivot_bars = int(params.get("pivot_bars", 5))
        component = str(params.get("component", "bias"))
        bias, bos = _market_structure_latest(df, pivot_bars=pivot_bars)

        if component == "bias":
            return float(bias)
        if component == "bos":
            return float(bos)
        raise ValueError(f"Unknown market_structure component: {component}")
