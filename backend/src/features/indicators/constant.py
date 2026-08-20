from __future__ import annotations

from typing import Any

import pandas as pd

from src.features.indicators.base import register_indicator


@register_indicator("constant")
class ConstantIndicator:
    """Fixed literal value, for use as a comparison baseline in flag expressions."""

    def compute(self, df: pd.DataFrame, params: dict[str, Any]) -> float:
        return float(params.get("value", 0.0))
