from __future__ import annotations

from typing import Any

import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators._helpers import _last_valid
from src.features.indicators.base import register_indicator


def _macd_components(
    df: pd.DataFrame,
    *,
    fast: int,
    slow: int,
    signal: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    min_bars = slow + signal
    if len(df) < min_bars:
        raise InsufficientDataError(f"Insufficient data for macd: need at least {min_bars} bars")
    close = df["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


@register_indicator("macd")
class MacdIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal = int(params.get("signal", 9))
        component = str(params.get("component", "line"))
        line, signal_line, histogram = _macd_components(df, fast=fast, slow=slow, signal=signal)

        if component == "line":
            min_periods = slow
            series = line
            name = "macd"
        elif component == "signal":
            min_periods = slow + signal
            series = signal_line
            name = "macd_signal"
        elif component == "histogram":
            min_periods = slow + signal
            series = histogram
            name = "macd_histogram"
        elif component == "histogram_slope":
            min_periods = slow + signal + 1
            if len(df) < min_periods:
                raise InsufficientDataError(
                    f"Insufficient data for macd histogram_slope: "
                    f"need at least {min_periods} bars"
                )
            valid_hist = histogram.dropna()
            if len(valid_hist) < 2:
                raise InsufficientDataError(
                    f"Insufficient data for macd histogram_slope: "
                    f"need at least {min_periods} bars"
                )
            return float(valid_hist.iloc[-1] - valid_hist.iloc[-2])
        else:
            raise ValueError(f"Unknown macd component: {component}")

        return _last_valid(series, name=name, min_periods=min_periods)
