from __future__ import annotations

import operator
import re

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

    def compute_indicator(self, definition: IndicatorDef, df) -> float:
        cls = get_indicator_class(definition.type)
        return cls().compute(df, definition.params)

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
