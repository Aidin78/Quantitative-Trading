from __future__ import annotations

from typing import Any

import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators.base import register_indicator


def _ema_cross_signal(df: pd.DataFrame, *, fast: int, slow: int) -> float:
    min_bars = slow + 1
    if len(df) < min_bars:
        raise InsufficientDataError(
            f"Insufficient data for ema_cross: need at least {min_bars} bars"
        )
    close = df["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    spread = (ema_fast - ema_slow).dropna()
    if len(spread) < 2:
        raise InsufficientDataError(
            f"Insufficient data for ema_cross: need at least {min_bars} bars"
        )
    prev_spread = spread.iloc[-2]
    curr_spread = spread.iloc[-1]
    if prev_spread <= 0 and curr_spread > 0:
        return 1.0
    if prev_spread >= 0 and curr_spread < 0:
        return -1.0
    return 0.0


@register_indicator("ema_cross")
class EmaCrossIndicator:
    """Crossover event (not state): +1 bullish cross, -1 bearish cross, 0 otherwise."""

    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        return _ema_cross_signal(df, fast=fast, slow=slow)
