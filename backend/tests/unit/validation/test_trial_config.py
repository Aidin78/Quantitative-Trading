from __future__ import annotations

from src.validation.trial_config import (
    SESSION_PRESETS,
    build_engine_config_from_trial,
    build_engine_write_patch,
    build_features_config_from_trial,
    build_features_write_kwargs,
    build_provider_overrides,
    build_provider_write_patches,
    build_validation_settings_patch,
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


def test_build_provider_overrides_includes_volume_order_flow() -> None:
    overrides = build_provider_overrides(
        {
            "vol_enabled": 1,
            "vol_weight": 0.75,
            "vol_period": 26,
            "min_cmf": 0.08,
            "min_volume_ratio": 1.5,
            "vol_require_price_align": 0,
        }
    )
    assert overrides["volume_order_flow"]["enabled"] is True
    assert overrides["volume_order_flow"]["weight"] == 0.75
    assert overrides["volume_order_flow"]["period"] == 26
    assert overrides["volume_order_flow"]["min_cmf"] == 0.08
    assert overrides["volume_order_flow"]["min_volume_ratio"] == 1.5
    assert overrides["volume_order_flow"]["require_price_align"] is False


def test_build_features_config_from_trial_changes_vol_period() -> None:
    config, _ = build_features_config_from_trial({"vol_period": 26})
    cmf = next(ind for ind in config.indicators if ind.name == "cmf_20")
    ratio = next(ind for ind in config.indicators if ind.name == "volume_ratio_20")
    assert cmf.params["period"] == 26
    assert ratio.params["period"] == 26


def test_build_provider_overrides_includes_market_structure() -> None:
    overrides = build_provider_overrides(
        {
            "ms_enabled": 1,
            "ms_weight": 0.85,
            "ms_pivot_bars": 7,
            "ms_require_bos": 0,
            "ms_require_trend": 1,
        }
    )
    assert overrides["market_structure"]["enabled"] is True
    assert overrides["market_structure"]["weight"] == 0.85
    assert overrides["market_structure"]["pivot_bars"] == 7
    assert overrides["market_structure"]["require_bos"] is False
    assert overrides["market_structure"]["require_trend"] is True


def test_build_features_config_from_trial_changes_ms_pivot_bars() -> None:
    config, _ = build_features_config_from_trial({"ms_pivot_bars": 7})
    bias = next(ind for ind in config.indicators if ind.name == "ms_bias")
    bos = next(ind for ind in config.indicators if ind.name == "ms_bos")
    assert bias.params["pivot_bars"] == 7
    assert bos.params["pivot_bars"] == 7


def _sample_trial() -> dict:
    return {
        "min_agreeing_providers": 2,
        "min_atr_pct": 0.25,
        "session_preset": "us_only",
        "min_confidence": 0.7,
        "min_risk_reward": 2.5,
        "max_signals_per_day": 8,
        "sl_atr_mult": 1.2,
        "tp_atr_mult": 2.8,
        "ema_enabled": 1,
        "ema_weight": 1.1,
        "require_trend": 0,
        "rsi_enabled": 0,
        "rsi_weight": 0.9,
        "oversold": 28.0,
        "overbought": 72.0,
        "avoid_high_vol": 0,
        "macd_enabled": 1,
        "macd_weight": 0.8,
        "require_signal_align": 0,
        "min_histogram_slope": 0.0002,
        "macd_require_trend": 1,
        "adx_enabled": 1,
        "adx_weight": 0.6,
        "min_adx": 22.0,
        "min_di_spread": 4.0,
        "adx_require_trend": 1,
        "bb_enabled": 0,
        "bb_weight": 0.5,
        "bb_avoid_high_vol": 0,
        "bb_max_adx": 30.0,
        "st_enabled": 1,
        "st_weight": 0.75,
        "st_require_trend": 1,
        "vol_enabled": 1,
        "vol_weight": 0.4,
        "vol_period": 18,
        "min_cmf": 0.08,
        "min_volume_ratio": 1.4,
        "vol_require_price_align": 0,
        "ms_enabled": 1,
        "ms_weight": 0.55,
        "ms_pivot_bars": 6,
        "ms_require_bos": 0,
        "ms_require_trend": 1,
        "max_bars_in_trade": 36,
        "risk_pct_per_trade": 1.5,
        "ema_fast": 10,
        "ema_slow": 30,
        "rsi_period": 12,
        "macd_fast": 10,
        "macd_slow": 28,
        "macd_signal_period": 8,
        "adx_period": 16,
        "bb_period": 22,
        "bb_std": 2.5,
        "st_period": 12,
        "st_multiplier": 2.5,
    }


def test_provider_write_patches_match_overrides() -> None:
    trial = _sample_trial()
    overrides = build_provider_overrides(trial)
    patches = build_provider_write_patches(trial)
    assert set(patches) == set(overrides)
    for provider_id, override in overrides.items():
        patch = patches[provider_id]
        assert patch["enabled"] is override["enabled"]
        assert patch["weight"] == override["weight"]
        assert patch["params"] == {
            key: value for key, value in override.items() if key not in {"enabled", "weight"}
        }


def test_engine_write_patch_matches_in_memory_engine_config() -> None:
    trial = _sample_trial()
    patch = build_engine_write_patch(trial)
    cfg = build_engine_config_from_trial(trial)
    assert patch["aggregation"]["min_agreeing_providers"] == cfg.aggregation.min_agreeing_providers
    assert patch["filter"]["min_atr_pct"] == cfg.filter.min_atr_pct
    assert tuple(patch["filter"]["allowed_sessions"]) == cfg.filter.allowed_sessions
    assert patch["risk"]["min_confidence"] == cfg.risk.min_confidence
    assert patch["risk"]["min_risk_reward"] == cfg.risk.min_risk_reward
    assert patch["risk"]["max_signals_per_day"] == cfg.risk.max_signals_per_day


def test_features_write_kwargs_match_features_config_from_trial() -> None:
    trial = _sample_trial()
    kwargs = build_features_write_kwargs(trial)
    config, _ = build_features_config_from_trial(trial)
    ema_fast = next(ind for ind in config.indicators if ind.name == "ema_12")
    ema_slow = next(ind for ind in config.indicators if ind.name == "ema_26")
    rsi = next(ind for ind in config.indicators if ind.name == "rsi_14")
    macd = next(ind for ind in config.indicators if ind.name == "macd")
    adx = next(ind for ind in config.indicators if ind.name == "adx_14")
    bb = next(ind for ind in config.indicators if ind.name == "bb_upper")
    st = next(ind for ind in config.indicators if ind.name == "supertrend")
    vol = next(ind for ind in config.indicators if ind.name == "cmf_20")
    ms = next(ind for ind in config.indicators if ind.name == "ms_bias")
    assert kwargs["ema_fast"] == ema_fast.params["period"]
    assert kwargs["ema_slow"] == ema_slow.params["period"]
    assert kwargs["rsi_period"] == rsi.params["period"]
    assert kwargs["macd_fast"] == macd.params["fast"]
    assert kwargs["macd_slow"] == macd.params["slow"]
    assert kwargs["macd_signal_period"] == macd.params["signal"]
    assert kwargs["adx_period"] == adx.params["period"]
    assert kwargs["bb_period"] == bb.params["period"]
    assert kwargs["bb_std"] == bb.params["std"]
    assert kwargs["st_period"] == st.params["period"]
    assert kwargs["st_multiplier"] == st.params["multiplier"]
    assert kwargs["vol_period"] == vol.params["period"]
    assert kwargs["ms_pivot_bars"] == ms.params["pivot_bars"]


def test_validation_settings_patch_from_trial() -> None:
    patch = build_validation_settings_patch(_sample_trial())
    assert patch == {"max_bars_in_trade": 36, "risk_pct_per_trade": 1.5}
