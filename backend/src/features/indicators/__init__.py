from __future__ import annotations

from typing import Any

import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators.base import register_indicator


def _last_valid(series: pd.Series, *, name: str, min_periods: int) -> float:
    valid = series.dropna()
    if len(valid) < 1:
        raise InsufficientDataError(
            f"Insufficient data for {name}: need at least {min_periods} bars"
        )
    return float(valid.iloc[-1])


@register_indicator("ema")
class EmaIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        period = int(params["period"])
        if len(df) < period:
            raise InsufficientDataError(f"Insufficient data for ema: need at least {period} bars")
        series = df["close"].ewm(span=period, adjust=False).mean()
        return _last_valid(series, name="ema", min_periods=period)


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


@register_indicator("atr")
class AtrIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        period = int(params["period"])
        if len(df) < period + 1:
            raise InsufficientDataError(
                f"Insufficient data for atr: need at least {period + 1} bars"
            )
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
        atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        return _last_valid(atr, name="atr", min_periods=period)


@register_indicator("macd")
class MacdIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal = int(params.get("signal", 9))
        min_bars = slow + signal
        if len(df) < min_bars:
            raise InsufficientDataError(
                f"Insufficient data for macd: need at least {min_bars} bars"
            )
        close = df["close"]
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        return _last_valid(macd_line, name="macd", min_periods=slow)


@register_indicator("bollinger")
class BollingerIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        period = int(params.get("period", 20))
        std_mult = float(params.get("std", 2))
        band = str(params.get("band", "middle"))
        if len(df) < period:
            raise InsufficientDataError(
                f"Insufficient data for bollinger: need at least {period} bars"
            )
        close = df["close"]
        middle = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        if band == "upper":
            series = middle + std_mult * std
        elif band == "lower":
            series = middle - std_mult * std
        else:
            series = middle
        return _last_valid(series, name=f"bollinger_{band}", min_periods=period)
