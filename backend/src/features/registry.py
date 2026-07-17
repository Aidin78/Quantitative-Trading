from __future__ import annotations

import operator
import re
from typing import Any

from src.features.config import FeaturesConfig, FlagDef, IndicatorDef
from src.features.indicators import base as _indicators_base  # noqa: F401 — registers indicators
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
        if definition.type == "macd" and shared is not None:
            return self._compute_macd_cached(df, definition.params, shared)
        cls = get_indicator_class(definition.type)
        return cls().compute(df, definition.params)

    def _compute_macd_cached(
        self,
        df,
        params: dict[str, Any],
        shared: dict[tuple[Any, ...], Any],
    ) -> float:
        from src.core.exceptions import InsufficientDataError
        from src.features.indicators import _last_valid, _macd_components

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
                    f"Insufficient data for macd histogram_slope: need at least {min_periods} bars"
                )
            valid_hist = histogram.dropna()
            if len(valid_hist) < 2:
                raise InsufficientDataError(
                    f"Insufficient data for macd histogram_slope: "
                    f"need at least {min_periods} bars"
                )
            return float(valid_hist.iloc[-1] - valid_hist.iloc[-2])
        raise ValueError(f"Unknown macd component: {component}")

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
