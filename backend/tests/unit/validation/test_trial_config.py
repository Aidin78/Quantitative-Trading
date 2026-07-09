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
        {"ema_fast": 10, "ema_slow": 30, "rsi_period": 12}
    )
    ema_fast = next(ind for ind in config.indicators if ind.name == "ema_12")
    ema_slow = next(ind for ind in config.indicators if ind.name == "ema_26")
    rsi = next(ind for ind in config.indicators if ind.name == "rsi_14")
    assert ema_fast.params["period"] == 10
    assert ema_slow.params["period"] == 30
    assert rsi.params["period"] == 12
    assert len(config_hash) == 16
