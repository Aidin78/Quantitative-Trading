from __future__ import annotations

from src.validation.trial_config import (
    SESSION_PRESETS,
    build_engine_config_from_trial,
    build_features_config_from_trial,
    build_provider_overrides,
)


def test_build_provider_overrides_includes_rsi_thresholds() -> None:
    overrides = build_provider_overrides(
        {
            "oversold": 25.0,
            "overbought": 75.0,
            "ema_enabled": 1,
            "rsi_enabled": 0,
        }
    )
    assert overrides["rsi_divergence"]["oversold"] == 25.0
    assert overrides["rsi_divergence"]["enabled"] is False


def test_build_engine_config_applies_session_preset() -> None:
    cfg = build_engine_config_from_trial({"session_preset": "all", "min_atr_pct": 0.1})
    assert cfg.filter.allowed_sessions == SESSION_PRESETS["all"]
    assert cfg.filter.min_atr_pct == 0.1


def test_build_features_config_from_trial_changes_periods() -> None:
    config, config_hash = build_features_config_from_trial(
        {
            "ema_fast": 10,
            "ema_slow": 30,
            "rsi_period": 12,
            "macd_fast": 10,
            "macd_slow": 28,
            "macd_signal_period": 8,
        }
    )
    ema_fast = next(ind for ind in config.indicators if ind.name == "ema_12")
    ema_slow = next(ind for ind in config.indicators if ind.name == "ema_26")
    rsi = next(ind for ind in config.indicators if ind.name == "rsi_14")
    macd = next(ind for ind in config.indicators if ind.name == "macd")
    assert ema_fast.params["period"] == 10
    assert ema_slow.params["period"] == 30
    assert rsi.params["period"] == 12
    assert macd.params["fast"] == 10
    assert macd.params["slow"] == 28
    assert macd.params["signal"] == 8
    assert len(config_hash) == 16


def test_build_provider_overrides_includes_macd() -> None:
    overrides = build_provider_overrides(
        {
            "macd_enabled": 0,
            "macd_weight": 0.8,
            "require_signal_align": 0,
            "min_histogram_slope": 0.0001,
        }
    )
    assert overrides["macd_momentum"]["enabled"] is False
    assert overrides["macd_momentum"]["weight"] == 0.8
    assert overrides["macd_momentum"]["require_signal_align"] is False
    assert overrides["macd_momentum"]["min_histogram_slope"] == 0.0001


def test_build_provider_overrides_includes_adx() -> None:
    overrides = build_provider_overrides(
        {
            "adx_enabled": 1,
            "adx_weight": 0.7,
            "min_adx": 22.0,
            "min_di_spread": 4.0,
            "adx_require_trend": 1,
        }
    )
    assert overrides["adx_trend_strength"]["enabled"] is True
    assert overrides["adx_trend_strength"]["weight"] == 0.7
    assert overrides["adx_trend_strength"]["min_adx"] == 22.0
    assert overrides["adx_trend_strength"]["min_di_spread"] == 4.0
    assert overrides["adx_trend_strength"]["require_trend"] is True


def test_build_features_config_from_trial_changes_adx_period() -> None:
    config, _ = build_features_config_from_trial({"adx_period": 16})
    adx = next(ind for ind in config.indicators if ind.name == "adx_14")
    plus_di = next(ind for ind in config.indicators if ind.name == "plus_di_14")
    minus_di = next(ind for ind in config.indicators if ind.name == "minus_di_14")
    assert adx.params["period"] == 16
    assert plus_di.params["period"] == 16
    assert minus_di.params["period"] == 16


def test_build_provider_overrides_includes_bollinger() -> None:
    overrides = build_provider_overrides(
        {
            "bb_enabled": 1,
            "bb_weight": 0.9,
            "bb_avoid_high_vol": 0,
            "bb_max_adx": 25.0,
        }
    )
    assert overrides["bollinger_reversion"]["enabled"] is True
    assert overrides["bollinger_reversion"]["weight"] == 0.9
    assert overrides["bollinger_reversion"]["avoid_high_vol"] is False
    assert overrides["bollinger_reversion"]["max_adx"] == 25.0


def test_build_features_config_from_trial_changes_bb_params() -> None:
    config, _ = build_features_config_from_trial({"bb_period": 22, "bb_std": 2.5})
    upper = next(ind for ind in config.indicators if ind.name == "bb_upper")
    lower = next(ind for ind in config.indicators if ind.name == "bb_lower")
    middle = next(ind for ind in config.indicators if ind.name == "bb_middle")
    assert upper.params["period"] == 22
    assert upper.params["std"] == 2.5
    assert lower.params["period"] == 22
    assert middle.params["std"] == 2.5


def test_build_provider_overrides_includes_supertrend() -> None:
    overrides = build_provider_overrides(
        {
            "st_enabled": 1,
            "st_weight": 0.8,
            "st_require_trend": 1,
        }
    )
    assert overrides["supertrend_trend"]["enabled"] is True
    assert overrides["supertrend_trend"]["weight"] == 0.8
    assert overrides["supertrend_trend"]["require_trend"] is True


def test_build_features_config_from_trial_changes_st_params() -> None:
    config, _ = build_features_config_from_trial({"st_period": 14, "st_multiplier": 4.0})
    line = next(ind for ind in config.indicators if ind.name == "supertrend")
    direction = next(ind for ind in config.indicators if ind.name == "supertrend_direction")
    assert line.params["period"] == 14
    assert line.params["multiplier"] == 4.0
    assert direction.params["period"] == 14
    assert direction.params["multiplier"] == 4.0
