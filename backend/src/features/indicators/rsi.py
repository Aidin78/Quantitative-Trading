from __future__ import annotations

from typing import Any

import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators._helpers import _last_valid
from src.features.indicators.base import register_indicator


@register_indicator("rsi")
class RsiIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        period = int(params["period"])
        if len(df) < period + 1:
            raise InsufficientDataError(
                f"Insufficient data for rsi: need at least {period + 1} bars"
            )
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + rs))
        return _last_valid(rsi, name="rsi", min_periods=period)
