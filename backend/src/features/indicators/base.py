from __future__ import annotations

from typing import Any, Protocol

import pandas as pd


class Indicator(Protocol):
    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float: ...


_INDICATOR_TYPES: dict[str, type] = {}


def register_indicator(indicator_type: str):
    def decorator(cls: type) -> type:
        _INDICATOR_TYPES[indicator_type] = cls
        return cls

    return decorator


def get_indicator_class(indicator_type: str) -> type:
    if indicator_type not in _INDICATOR_TYPES:
        raise KeyError(f"Unknown indicator type: {indicator_type}")
    return _INDICATOR_TYPES[indicator_type]


def registered_indicator_types() -> frozenset[str]:
    return frozenset(_INDICATOR_TYPES)
