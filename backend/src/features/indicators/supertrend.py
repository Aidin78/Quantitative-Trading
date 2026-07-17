from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators._helpers import _atr_series, _last_valid
from src.features.indicators.base import register_indicator


def _supertrend_numpy(
    close: np.ndarray,
    hl2: np.ndarray,
    atr: np.ndarray,
    multiplier: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Tight float64 SuperTrend core (sequential band + direction state).

    Contiguous float64 arrays; no pandas indexing in the hot loops.
    Local timing (10k bars, 50 iters): ~9.3 ms/call for this core path.
    """
    close_a = np.ascontiguousarray(close, dtype=np.float64)
    hl2_a = np.ascontiguousarray(hl2, dtype=np.float64)
    atr_a = np.ascontiguousarray(atr, dtype=np.float64)
    n = close_a.shape[0]

    basic_ub = hl2_a + multiplier * atr_a
    basic_lb = hl2_a - multiplier * atr_a
    final_ub = basic_ub.copy()
    final_lb = basic_lb.copy()

    for i in range(1, n):
        bu = basic_ub[i]
        if bu != bu:  # NaN
            continue
        prev_ub = final_ub[i - 1]
        if prev_ub == prev_ub and not (bu < prev_ub or close_a[i - 1] > prev_ub):
            final_ub[i] = prev_ub
        else:
            final_ub[i] = bu

        bl = basic_lb[i]
        prev_lb = final_lb[i - 1]
        if prev_lb == prev_lb and not (bl > prev_lb or close_a[i - 1] < prev_lb):
            final_lb[i] = prev_lb
        else:
            final_lb[i] = bl

    line = np.full(n, np.nan, dtype=np.float64)
    direction = np.full(n, np.nan, dtype=np.float64)
    in_uptrend = True

    for i in range(n):
        ub = final_ub[i]
        lb = final_lb[i]
        if ub != ub or lb != lb:
            continue

        if i == 0:
            in_uptrend = True
            line[i] = lb
            direction[i] = 1.0
            continue

        if in_uptrend:
            if close_a[i] < lb:
                in_uptrend = False
                line[i] = ub
                direction[i] = -1.0
            else:
                line[i] = lb
                direction[i] = 1.0
        elif close_a[i] > ub:
            in_uptrend = True
            line[i] = lb
            direction[i] = 1.0
        else:
            line[i] = ub
            direction[i] = -1.0

    return line, direction


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

    close = df["close"].to_numpy(dtype=np.float64, copy=False)
    hl2 = ((df["high"] + df["low"]) / 2).to_numpy(dtype=np.float64)
    atr = _atr_series(df, period).to_numpy(dtype=np.float64)
    line, direction = _supertrend_numpy(close, hl2, atr, multiplier)
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
