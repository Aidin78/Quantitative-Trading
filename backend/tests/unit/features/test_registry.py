from __future__ import annotations

import pytest

from src.features.config import load_features_config
from src.features.registry import FeatureRegistry
from tests.fixtures.ohlcv import make_sample_ohlcv


def test_load_features_config() -> None:
    load_features_config.cache_clear()
    config, config_hash = load_features_config()
    assert config.version == "v1"
    assert len(config.indicators) >= 9
    assert config.flags[0].name == "ema_cross_bullish"
    assert len(config_hash) == 64
    load_features_config.cache_clear()


def test_registry_evaluates_flags() -> None:
    config, _ = load_features_config()
    registry = FeatureRegistry(config)
    indicators = {
        "ema_12": 100.0,
        "ema_26": 90.0,
        "macd": 0.0025,
        "macd_signal": 0.0018,
    }
    flags = registry.evaluate_flags(indicators)
    assert flags["ema_cross_bullish"] is True
    assert flags["macd_bullish"] is True
    assert flags["macd_bearish"] is False


def test_registry_compute_all_indicators() -> None:
    config, _ = load_features_config()
    registry = FeatureRegistry(config)
    df = make_sample_ohlcv()
    values = {d.name: registry.compute_indicator(d, df) for d in registry.indicators}
    assert set(values) == {d.name for d in registry.indicators}


def test_registry_rejects_invalid_flag_expr() -> None:
    from src.features.config import FeaturesConfig, FlagDef

    config, _ = load_features_config()
    bad = FeaturesConfig(
        version=config.version,
        indicators=config.indicators,
        flags=(FlagDef(name="bad", expr="ema_12 + ema_26"),),
        context=config.context,
    )
    registry = FeatureRegistry(bad)
    with pytest.raises(ValueError):
        registry.evaluate_flags({"ema_12": 1.0, "ema_26": 2.0})
