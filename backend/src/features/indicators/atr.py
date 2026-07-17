from __future__ import annotations

from typing import Any

import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators._helpers import _atr_series, _last_valid
from src.features.indicators.base import register_indicator


@register_indicator("atr")
class AtrIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        period = int(params["period"])
        if len(df) < period + 1:
            raise InsufficientDataError(
                f"Insufficient data for atr: need at least {period + 1} bars"
            )
        atr = _atr_series(df, period)
        return _last_valid(atr, name="atr", min_periods=period)
