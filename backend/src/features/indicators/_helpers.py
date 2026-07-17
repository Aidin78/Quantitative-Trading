from __future__ import annotations

import pandas as pd

from src.core.exceptions import InsufficientDataError


def _last_valid(series: pd.Series, *, name: str, min_periods: int) -> float:
    valid = series.dropna()
    if len(valid) < 1:
        raise InsufficientDataError(
            f"Insufficient data for {name}: need at least {min_periods} bars"
        )
    return float(valid.iloc[-1])


def _atr_series(df: pd.DataFrame, period: int) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
