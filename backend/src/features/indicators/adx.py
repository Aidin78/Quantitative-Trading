from __future__ import annotations

from typing import Any

import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators._helpers import _last_valid
from src.features.indicators.base import register_indicator


def _adx_components(
    df: pd.DataFrame,
    *,
    period: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    min_bars = 2 * period
    if len(df) < min_bars:
        raise InsufficientDataError(f"Insufficient data for adx: need at least {min_bars} bars")

    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    alpha = 1 / period
    atr = tr.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

    atr_safe = atr.replace(0, pd.NA)
    plus_di = 100 * plus_dm_smooth / atr_safe
    minus_di = 100 * minus_dm_smooth / atr_safe

    di_sum = (plus_di + minus_di).replace(0, pd.NA)
    dx = (100 * (plus_di - minus_di).abs() / di_sum).fillna(0.0)
    adx = dx.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

    return adx, plus_di, minus_di


@register_indicator("adx")
class AdxIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        period = int(params.get("period", 14))
        component = str(params.get("component", "adx"))
        adx, plus_di, minus_di = _adx_components(df, period=period)

        if component == "adx":
            min_periods = 2 * period
            series = adx
            name = "adx"
        elif component == "plus_di":
            min_periods = period + 1
            series = plus_di
            name = "plus_di"
        elif component == "minus_di":
            min_periods = period + 1
            series = minus_di
            name = "minus_di"
        else:
            raise ValueError(f"Unknown adx component: {component}")

        return _last_valid(series, name=name, min_periods=min_periods)
