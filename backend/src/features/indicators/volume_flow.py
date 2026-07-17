from __future__ import annotations

from typing import Any

import pandas as pd

from src.core.exceptions import InsufficientDataError
from src.features.indicators._helpers import _last_valid
from src.features.indicators.base import register_indicator


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
