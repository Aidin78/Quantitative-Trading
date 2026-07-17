from __future__ import annotations

import operator
import re
from typing import Any

from src.features import indicators as _indicators  # noqa: F401 — registers indicator types
from src.features.config import FeaturesConfig, FlagDef, IndicatorDef
from src.features.indicators.base import get_indicator_class

_COMPARATORS = [
    (">=", operator.ge),
    ("<=", operator.le),
    (">", operator.gt),
    ("<", operator.lt),
    ("==", operator.eq),
]
_FLAG_PATTERN = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|<=|==|>|<)\s*([a-zA-Z_][a-zA-Z0-9_]*)$"
)
_SHARED_COMPONENT_TYPES = frozenset(
    {"macd", "adx", "bollinger", "supertrend", "volume_flow", "market_structure"}
)


class FeatureRegistry:
    def __init__(self, config: FeaturesConfig) -> None:
        self._config = config

    @property
    def config(self) -> FeaturesConfig:
        return self._config

    @property
    def indicators(self) -> tuple[IndicatorDef, ...]:
        return self._config.indicators

    @property
    def flags(self) -> tuple[FlagDef, ...]:
        return self._config.flags

    def compute_indicator(
        self,
        definition: IndicatorDef,
        df,
        *,
        shared: dict[tuple[Any, ...], Any] | None = None,
    ) -> float:
        if shared is not None and definition.type in _SHARED_COMPONENT_TYPES:
            return self._compute_shared_component(definition, df, shared)
        cls = get_indicator_class(definition.type)
        return cls().compute(df, definition.params)

    def _compute_shared_component(
        self,
        definition: IndicatorDef,
        df,
        shared: dict[tuple[Any, ...], Any],
    ) -> float:
        from src.core.exceptions import InsufficientDataError
        from src.features.indicators import (
            _adx_components,
            _bollinger_components,
            _last_valid,
            _macd_components,
            _market_structure_latest,
            _supertrend_components,
            _volume_flow_components,
        )

        params = definition.params
        indicator_type = definition.type

        if indicator_type == "macd":
            fast = int(params.get("fast", 12))
            slow = int(params.get("slow", 26))
            signal = int(params.get("signal", 9))
            component = str(params.get("component", "line"))
            key = ("macd", fast, slow, signal)
            if key not in shared:
                shared[key] = _macd_components(df, fast=fast, slow=slow, signal=signal)
            line, signal_line, histogram = shared[key]
            if component == "line":
                return _last_valid(line, name="macd", min_periods=slow)
            if component == "signal":
                return _last_valid(signal_line, name="macd_signal", min_periods=slow + signal)
            if component == "histogram":
                return _last_valid(histogram, name="macd_histogram", min_periods=slow + signal)
            if component == "histogram_slope":
                min_periods = slow + signal + 1
                if len(df) < min_periods:
                    raise InsufficientDataError(
                        "Insufficient data for macd histogram_slope: "
                        f"need at least {min_periods} bars"
                    )
                valid_hist = histogram.dropna()
                if len(valid_hist) < 2:
                    raise InsufficientDataError(
                        "Insufficient data for macd histogram_slope: "
                        f"need at least {min_periods} bars"
                    )
                return float(valid_hist.iloc[-1] - valid_hist.iloc[-2])
            raise ValueError(f"Unknown macd component: {component}")

        if indicator_type == "adx":
            period = int(params.get("period", 14))
            component = str(params.get("component", "adx"))
            key = ("adx", period)
            if key not in shared:
                shared[key] = _adx_components(df, period=period)
            adx, plus_di, minus_di = shared[key]
            if component == "adx":
                return _last_valid(adx, name="adx", min_periods=2 * period)
            if component == "plus_di":
                return _last_valid(plus_di, name="plus_di", min_periods=period + 1)
            if component == "minus_di":
                return _last_valid(minus_di, name="minus_di", min_periods=period + 1)
            raise ValueError(f"Unknown adx component: {component}")

        if indicator_type == "bollinger":
            period = int(params.get("period", 20))
            std_mult = float(params.get("std", 2))
            band = str(params.get("band", "middle"))
            key = ("bollinger", period, std_mult)
            if key not in shared:
                shared[key] = _bollinger_components(df, period=period, std_mult=std_mult)
            upper, middle, lower = shared[key]
            if band == "upper":
                series = upper
            elif band == "lower":
                series = lower
            else:
                series = middle
            return _last_valid(series, name=f"bollinger_{band}", min_periods=period)

        if indicator_type == "supertrend":
            period = int(params.get("period", 10))
            multiplier = float(params.get("multiplier", 3.0))
            component = str(params.get("component", "line"))
            key = ("supertrend", period, multiplier)
            if key not in shared:
                shared[key] = _supertrend_components(df, period=period, multiplier=multiplier)
            line, direction = shared[key]
            if component == "line":
                return _last_valid(line, name="supertrend", min_periods=2 * period)
            if component == "direction":
                return _last_valid(direction, name="supertrend_direction", min_periods=2 * period)
            raise ValueError(f"Unknown supertrend component: {component}")

        if indicator_type == "volume_flow":
            period = int(params.get("period", 20))
            component = str(params.get("component", "cmf"))
            if component == "close_delta":
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
            key = ("volume_flow", period)
            if key not in shared:
                shared[key] = _volume_flow_components(df, period=period)
            cmf, volume_ratio = shared[key]
            if component == "cmf":
                return _last_valid(cmf, name="cmf", min_periods=period)
            if component == "volume_ratio":
                return _last_valid(volume_ratio, name="volume_ratio", min_periods=period)
            raise ValueError(f"Unknown volume_flow component: {component}")

        if indicator_type == "market_structure":
            pivot_bars = int(params.get("pivot_bars", 5))
            component = str(params.get("component", "bias"))
            key = ("market_structure", pivot_bars)
            if key not in shared:
                shared[key] = _market_structure_latest(df, pivot_bars=pivot_bars)
            bias, bos = shared[key]
            if component == "bias":
                return float(bias)
            if component == "bos":
                return float(bos)
            raise ValueError(f"Unknown market_structure component: {component}")

        raise ValueError(f"Unsupported shared indicator type: {indicator_type}")

    def evaluate_flag(self, flag: FlagDef, indicators: dict[str, float]) -> bool:
        match = _FLAG_PATTERN.match(flag.expr.strip())
        if not match:
            raise ValueError(f"Unsupported flag expression: {flag.expr}")
        left_name, op_str, right_name = match.groups()
        if left_name not in indicators or right_name not in indicators:
            raise KeyError(f"Flag references unknown indicator in: {flag.expr}")
        left_val = indicators[left_name]
        right_val = indicators[right_name]
        for token, func in _COMPARATORS:
            if token == op_str:
                return bool(func(left_val, right_val))
        raise ValueError(f"Unsupported operator in flag: {flag.expr}")

    def evaluate_flags(self, indicators: dict[str, float]) -> dict[str, bool]:
        return {flag.name: self.evaluate_flag(flag, indicators) for flag in self._config.flags}
