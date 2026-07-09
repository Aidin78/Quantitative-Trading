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


def _supertrend_components(
    df: pd.DataFrame,
    *,
    period: int,
    multiplier: float,
) -> tuple[pd.Series, pd.Series]:
    min_bars = 2 * period
    if len(df) < min_bars:
        raise InsufficientDataError(
            f"Insufficient data for supertrend: need at least {min_bars} bars"
        )

    close = df["close"].to_numpy(dtype=float)
    hl2 = ((df["high"] + df["low"]) / 2).to_numpy(dtype=float)
    atr = _atr_series(df, period).to_numpy(dtype=float)
    n = len(df)

    basic_ub = hl2 + multiplier * atr
    basic_lb = hl2 - multiplier * atr
    final_ub = basic_ub.copy()
    final_lb = basic_lb.copy()

    for i in range(1, n):
        if not pd.notna(basic_ub[i]):
            continue
        if pd.notna(final_ub[i - 1]) and (
            basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]
        ):
            final_ub[i] = basic_ub[i]
        elif pd.notna(final_ub[i - 1]):
            final_ub[i] = final_ub[i - 1]
        else:
            final_ub[i] = basic_ub[i]

        if pd.notna(final_lb[i - 1]) and (
            basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]
        ):
            final_lb[i] = basic_lb[i]
        elif pd.notna(final_lb[i - 1]):
            final_lb[i] = final_lb[i - 1]
        else:
            final_lb[i] = basic_lb[i]

    line = [float("nan")] * n
    direction = [float("nan")] * n
    in_uptrend = True

    for i in range(n):
        if not pd.notna(final_ub[i]) or not pd.notna(final_lb[i]):
            continue

        if i == 0:
            in_uptrend = True
            line[i] = final_lb[i]
            direction[i] = 1.0
            continue

        if in_uptrend:
            line[i] = final_lb[i]
            direction[i] = 1.0
            if close[i] < final_lb[i]:
                in_uptrend = False
                line[i] = final_ub[i]
                direction[i] = -1.0
        else:
            line[i] = final_ub[i]
            direction[i] = -1.0
            if close[i] > final_ub[i]:
                in_uptrend = True
                line[i] = final_lb[i]
                direction[i] = 1.0

    return pd.Series(line, index=df.index), pd.Series(direction, index=df.index)


@register_indicator("supertrend")
class SuperTrendIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        period = int(params.get("period", 10))
        multiplier = float(params.get("multiplier", 3.0))
        component = str(params.get("component", "line"))
        line, direction = _supertrend_components(df, period=period, multiplier=multiplier)

        if component == "line":
            series = line
            name = "supertrend"
        elif component == "direction":
            series = direction
            name = "supertrend_direction"
        else:
            raise ValueError(f"Unknown supertrend component: {component}")

        return _last_valid(series, name=name, min_periods=2 * period)


def _volume_flow_components(
    df: pd.DataFrame,
    *,
    period: int,
) -> tuple[pd.Series, pd.Series]:
    if len(df) < period:
        raise InsufficientDataError(
            f"Insufficient data for volume_flow: need at least {period} bars"
        )
    if "volume" not in df.columns:
        raise InsufficientDataError("volume column required for volume_flow indicator")

    high = df["high"]
    low = df["low"]
    close = df["close"]
    volume = df["volume"].astype(float)

    hl_range = (high - low).astype(float)
    mf_mult = ((close - low) - (high - close)) / hl_range
    mf_mult = mf_mult.where(hl_range.notna(), 0.0).fillna(0.0)
    mf_volume = mf_mult * volume

    cmf = mf_volume.rolling(window=period).sum() / volume.rolling(window=period).sum()
    vol_sma = volume.rolling(window=period).mean()
    volume_ratio = volume / vol_sma.replace(0, pd.NA)

    return cmf, volume_ratio


@register_indicator("volume_flow")
class VolumeFlowIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        period = int(params.get("period", 20))
        component = str(params.get("component", "cmf"))
        cmf, volume_ratio = _volume_flow_components(df, period=period)

        if component == "cmf":
            series = cmf
            name = "cmf"
            min_periods = period
        elif component == "volume_ratio":
            series = volume_ratio
            name = "volume_ratio"
            min_periods = period
        elif component == "close_delta":
            if len(df) < 2:
                raise InsufficientDataError(
                    "Insufficient data for volume_flow close_delta: need at least 2 bars"
                )
            valid_close = df["close"].dropna()
            if len(valid_close) < 2:
                raise InsufficientDataError(
                    "Insufficient data for volume_flow close_delta: need at least 2 bars"
                )
            return float(valid_close.iloc[-1] - valid_close.iloc[-2])
        else:
            raise ValueError(f"Unknown volume_flow component: {component}")

        return _last_valid(series, name=name, min_periods=min_periods)


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


def _market_structure_components(
    df: pd.DataFrame,
    *,
    pivot_bars: int,
) -> tuple[pd.Series, pd.Series]:
    min_bars = 4 * pivot_bars + 1
    if len(df) < min_bars:
        raise InsufficientDataError(
            f"Insufficient data for market_structure: need at least {min_bars} bars"
        )

    n = len(df)
    bias_values = [float("nan")] * n
    bos_values = [float("nan")] * n
    close_series = df["close"]

    for t in range(min_bars - 1, n):
        highs, lows = _find_confirmed_pivots(df, pivot_bars=pivot_bars, up_to_index=t)
        bias_values[t] = _structure_bias(highs, lows)
        bos_values[t] = _structure_bos(float(close_series.iloc[t]), highs, lows)

    index = df.index
    return pd.Series(bias_values, index=index), pd.Series(bos_values, index=index)


@register_indicator("market_structure")
class MarketStructureIndicator:
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        pivot_bars = int(params.get("pivot_bars", 5))
        component = str(params.get("component", "bias"))
        bias, bos = _market_structure_components(df, pivot_bars=pivot_bars)
        min_periods = 4 * pivot_bars + 1

        if component == "bias":
            series = bias
            name = "ms_bias"
        elif component == "bos":
            series = bos
            name = "ms_bos"
        else:
            raise ValueError(f"Unknown market_structure component: {component}")

        return _last_valid(series, name=name, min_periods=min_periods)
