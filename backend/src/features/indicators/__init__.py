"""Indicator package: registration side-effects and compatibility re-exports."""

from __future__ import annotations

from src.features.indicators._helpers import _atr_series, _last_valid
from src.features.indicators.adx import AdxIndicator, _adx_components
from src.features.indicators.atr import AtrIndicator
from src.features.indicators.bollinger import BollingerIndicator, _bollinger_components
from src.features.indicators.ema import EmaIndicator
from src.features.indicators.macd import MacdIndicator, _macd_components
from src.features.indicators.market_structure import (
    MarketStructureIndicator,
    _market_structure_latest,
)
from src.features.indicators.rsi import RsiIndicator
from src.features.indicators.supertrend import (
    SuperTrendIndicator,
    _supertrend_components,
    _supertrend_numpy,
)
from src.features.indicators.volume_flow import VolumeFlowIndicator, _volume_flow_components

__all__ = [
    "AdxIndicator",
    "AtrIndicator",
    "BollingerIndicator",
    "EmaIndicator",
    "MacdIndicator",
    "MarketStructureIndicator",
    "RsiIndicator",
    "SuperTrendIndicator",
    "VolumeFlowIndicator",
    "_adx_components",
    "_atr_series",
    "_bollinger_components",
    "_last_valid",
    "_macd_components",
    "_market_structure_latest",
    "_supertrend_components",
    "_supertrend_numpy",
    "_volume_flow_components",
]
