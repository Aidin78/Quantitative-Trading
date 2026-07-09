from __future__ import annotations

from src.features.config import load_features_config


def compute_min_lookback_bars(config_dir=None) -> int:  # noqa: ANN001
    """Minimum prior bars required before the first validation cycle."""
    config, _ = load_features_config(config_dir)
    max_period = 1
    for indicator in config.indicators:
        params = indicator.params
        if indicator.type == "macd":
            component = str(params.get("component", "line"))
            needed = int(params.get("slow", 26)) + int(params.get("signal", 9))
            if component == "histogram_slope":
                needed += 1
        elif indicator.type == "bollinger":
            needed = int(params.get("period", 20))
        elif indicator.type == "supertrend":
            needed = 2 * int(params.get("period", 10))
        elif indicator.type == "volume_flow":
            component = str(params.get("component", "cmf"))
            if component == "close_delta":
                needed = 2
            else:
                needed = int(params.get("period", 20))
        else:
            needed = int(params.get("period", 14))
        max_period = max(max_period, needed)
    return max_period + 1
