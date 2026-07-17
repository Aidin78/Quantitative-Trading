from __future__ import annotations

from typing import Any

import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators._helpers import _last_valid
from src.features.indicators.base import register_indicator


@register_indicator("ema")
class EmaIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        period = int(params["period"])
        if len(df) < period:
            raise InsufficientDataError(f"Insufficient data for ema: need at least {period} bars")
        series = df["close"].ewm(span=period, adjust=False).mean()
        return _last_valid(series, name="ema", min_periods=period)
