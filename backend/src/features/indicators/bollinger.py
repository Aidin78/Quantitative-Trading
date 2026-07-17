from __future__ import annotations

from typing import Any

import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators._helpers import _last_valid
from src.features.indicators.base import register_indicator


def _bollinger_components(
    df: pd.DataFrame,
    *,
    period: int,
    std_mult: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    if len(df) < period:
        raise InsufficientDataError(f"Insufficient data for bollinger: need at least {period} bars")
    close = df["close"]
    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = middle + std_mult * std
    lower = middle - std_mult * std
    return upper, middle, lower


@register_indicator("bollinger")
class BollingerIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        period = int(params.get("period", 20))
        std_mult = float(params.get("std", 2))
        band = str(params.get("band", "middle"))
        upper, middle, lower = _bollinger_components(df, period=period, std_mult=std_mult)
        if band == "upper":
            series = upper
        elif band == "lower":
            series = lower
        else:
            series = middle
        return _last_valid(series, name=f"bollinger_{band}", min_periods=period)
