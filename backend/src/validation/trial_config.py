from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from src.core.contracts.governance import ConfigRevision
from src.core.contracts.provider import SignalProvider
from src.engine.config import EngineConfig, load_engine_config, resolve_config_dir
from src.execution.config import (
    ValidationExecutionConfig,
    load_default_fill_model,
    load_validation_execution_config,
)
from src.features.config import FeaturesConfig, IndicatorDef, load_features_config
from src.providers.registry import discover_provider_configs, instantiate_provider

SESSION_PRESETS: dict[str, tuple[str, ...]] = {
    "eu_us": ("EUROPE", "US", "OVERLAP"),
    "us_only": ("US",),
    "all": ("ASIA", "EUROPE", "US", "OVERLAP"),
}


def _session_preset(preset: str) -> tuple[str, ...]:
    return SESSION_PRESETS.get(preset, SESSION_PRESETS["eu_us"])


def build_engine_config_from_trial(
    trial: dict[str, Any], base: EngineConfig | None = None
) -> EngineConfig:
    cfg = base or load_engine_config()
    aggregation = cfg.aggregation.model_copy(
        update={
            "min_agreeing_providers": int(
                trial.get("min_agreeing_providers", cfg.aggregation.min_agreeing_providers)
            ),
        }
    )
    risk = cfg.risk.model_copy(
        update={
            "min_confidence": float(trial.get("min_confidence", cfg.risk.min_confidence)),
            "min_risk_reward": float(trial.get("min_risk_reward", cfg.risk.min_risk_reward)),
            "max_signals_per_day": int(
                trial.get("max_signals_per_day", cfg.risk.max_signals_per_day)
            ),
        }
    )
    filter_cfg = cfg.filter.model_copy(
        update={
            "min_atr_pct": float(trial.get("min_atr_pct", cfg.filter.min_atr_pct)),
            "allowed_sessions": _session_preset(str(trial.get("session_preset", "eu_us"))),
        }
    )
    return cfg.model_copy(update={"aggregation": aggregation, "risk": risk, "filter": filter_cfg})


def build_provider_overrides(trial: dict[str, Any]) -> dict[str, dict[str, Any]]:
    min_confidence = float(trial.get("min_confidence", 0.65))
    sl_atr_mult = float(trial.get("sl_atr_mult", 1.5))
    tp_atr_mult = float(trial.get("tp_atr_mult", 3.0))
    ema_shared = {
        "min_confidence": min_confidence,
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
        "weight": float(trial.get("ema_weight", 1.0)),
        "enabled": bool(int(trial.get("ema_enabled", 1))),
        "require_trend": bool(int(trial.get("require_trend", 1))),
    }
    rsi_shared = {
        "min_confidence": min_confidence,
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
        "oversold": float(trial.get("oversold", 30.0)),
        "overbought": float(trial.get("overbought", 70.0)),
        "weight": float(trial.get("rsi_weight", 1.0)),
        "enabled": bool(int(trial.get("rsi_enabled", 1))),
        "avoid_high_vol": bool(int(trial.get("avoid_high_vol", 1))),
    }
    macd_shared = {
        "min_confidence": min_confidence,
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
        "weight": float(trial.get("macd_weight", 1.0)),
        "enabled": bool(int(trial.get("macd_enabled", 1))),
        "require_signal_align": bool(int(trial.get("require_signal_align", 1))),
        "min_histogram_slope": float(trial.get("min_histogram_slope", 0.0)),
        "require_trend": bool(int(trial.get("macd_require_trend", 0))),
    }
    adx_shared = {
        "min_confidence": min_confidence,
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
        "weight": float(trial.get("adx_weight", 1.0)),
        "enabled": bool(int(trial.get("adx_enabled", 0))),
        "min_adx": float(trial.get("min_adx", 25.0)),
        "min_di_spread": float(trial.get("min_di_spread", 5.0)),
        "require_trend": bool(int(trial.get("adx_require_trend", 0))),
    }
    bb_shared = {
        "min_confidence": min_confidence,
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
        "weight": float(trial.get("bb_weight", 1.0)),
        "enabled": bool(int(trial.get("bb_enabled", 0))),
        "avoid_high_vol": bool(int(trial.get("bb_avoid_high_vol", 1))),
        "max_adx": float(trial.get("bb_max_adx", 0.0)),
    }
    st_shared = {
        "min_confidence": min_confidence,
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
        "weight": float(trial.get("st_weight", 1.0)),
        "enabled": bool(int(trial.get("st_enabled", 0))),
        "require_trend": bool(int(trial.get("st_require_trend", 0))),
    }
    vol_shared = {
        "min_confidence": min_confidence,
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
        "weight": float(trial.get("vol_weight", 1.0)),
        "enabled": bool(int(trial.get("vol_enabled", 0))),
        "period": int(trial.get("vol_period", 20)),
        "min_cmf": float(trial.get("min_cmf", 0.05)),
        "min_volume_ratio": float(trial.get("min_volume_ratio", 1.2)),
        "require_price_align": bool(int(trial.get("vol_require_price_align", 1))),
    }
    ms_shared = {
        "min_confidence": min_confidence,
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
        "weight": float(trial.get("ms_weight", 1.0)),
        "enabled": bool(int(trial.get("ms_enabled", 0))),
        "pivot_bars": int(trial.get("ms_pivot_bars", 5)),
        "require_bos": bool(int(trial.get("ms_require_bos", 1))),
        "require_trend": bool(int(trial.get("ms_require_trend", 0))),
    }
    return {
        "ema_crossover": ema_shared,
        "rsi_divergence": rsi_shared,
        "macd_momentum": macd_shared,
        "adx_trend_strength": adx_shared,
        "bollinger_reversion": bb_shared,
        "supertrend_trend": st_shared,
        "volume_order_flow": vol_shared,
        "market_structure": ms_shared,
    }


def build_execution_config_from_trial(
    trial: dict[str, Any],
    base: ValidationExecutionConfig | None = None,
) -> ValidationExecutionConfig:
    cfg = base or load_validation_execution_config()
    return cfg.model_copy(
        update={
            "max_bars_in_trade": int(trial.get("max_bars_in_trade", cfg.max_bars_in_trade)),
            "risk_pct_per_trade": float(trial.get("risk_pct_per_trade", cfg.risk_pct_per_trade)),
        }
    )


def build_features_config_from_trial(
    trial: dict[str, Any],
) -> tuple[FeaturesConfig, str]:
    base_config, _ = load_features_config()
    ema_fast = int(trial.get("ema_fast", 12))
    ema_slow = int(trial.get("ema_slow", 26))
    rsi_period = int(trial.get("rsi_period", 14))
    macd_fast = int(trial.get("macd_fast", 12))
    macd_slow = int(trial.get("macd_slow", 26))
    macd_signal_period = int(trial.get("macd_signal_period", 9))
    adx_period = int(trial.get("adx_period", 14))
    bb_period = int(trial.get("bb_period", 20))
    bb_std = float(trial.get("bb_std", 2.0))
    st_period = int(trial.get("st_period", 10))
    st_multiplier = float(trial.get("st_multiplier", 3.0))
    vol_period = int(trial.get("vol_period", 20))
    ms_pivot_bars = int(trial.get("ms_pivot_bars", 5))

    macd_names = {"macd", "macd_signal", "macd_histogram", "macd_histogram_slope"}
    adx_names = {"adx_14", "plus_di_14", "minus_di_14"}
    bb_names = {"bb_upper", "bb_lower", "bb_middle"}
    st_names = {"supertrend", "supertrend_direction"}
    vol_names = {"cmf_20", "volume_ratio_20"}
    ms_names = {"ms_bias", "ms_bos"}
    indicators: list[IndicatorDef] = []
    for indicator in base_config.indicators:
        if indicator.name == "ema_12":
            indicators.append(IndicatorDef(name="ema_12", type="ema", params={"period": ema_fast}))
        elif indicator.name == "ema_26":
            indicators.append(IndicatorDef(name="ema_26", type="ema", params={"period": ema_slow}))
        elif indicator.name == "rsi_14":
            indicators.append(
                IndicatorDef(name="rsi_14", type="rsi", params={"period": rsi_period})
            )
        elif indicator.name in macd_names:
            params = dict(indicator.params)
            params["fast"] = macd_fast
            params["slow"] = macd_slow
            params["signal"] = macd_signal_period
            indicators.append(IndicatorDef(name=indicator.name, type=indicator.type, params=params))
        elif indicator.name in adx_names:
            params = dict(indicator.params)
            params["period"] = adx_period
            indicators.append(IndicatorDef(name=indicator.name, type=indicator.type, params=params))
        elif indicator.name in bb_names:
            params = dict(indicator.params)
            params["period"] = bb_period
            params["std"] = bb_std
            indicators.append(IndicatorDef(name=indicator.name, type=indicator.type, params=params))
        elif indicator.name in st_names:
            params = dict(indicator.params)
            params["period"] = st_period
            params["multiplier"] = st_multiplier
            indicators.append(IndicatorDef(name=indicator.name, type=indicator.type, params=params))
        elif indicator.name in vol_names:
            params = dict(indicator.params)
            params["period"] = vol_period
            indicators.append(IndicatorDef(name=indicator.name, type=indicator.type, params=params))
        elif indicator.name in ms_names:
            params = dict(indicator.params)
            params["pivot_bars"] = ms_pivot_bars
            indicators.append(IndicatorDef(name=indicator.name, type=indicator.type, params=params))
        else:
            indicators.append(indicator)

    config = FeaturesConfig(
        version=base_config.version,
        indicators=tuple(indicators),
        flags=base_config.flags,
        context=base_config.context,
    )
    payload = json.dumps(
        {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "rsi_period": rsi_period,
            "macd_fast": macd_fast,
            "macd_slow": macd_slow,
            "macd_signal_period": macd_signal_period,
            "adx_period": adx_period,
            "bb_period": bb_period,
            "bb_std": bb_std,
            "st_period": st_period,
            "st_multiplier": st_multiplier,
            "vol_period": vol_period,
            "ms_pivot_bars": ms_pivot_bars,
        },
        sort_keys=True,
    )
    config_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return config, config_hash


def build_providers_from_overrides(
    provider_overrides: dict[str, dict[str, Any]] | None = None,
) -> list[SignalProvider]:
    providers: list[SignalProvider] = []
    for cfg in discover_provider_configs(resolve_config_dir()):
        params = dict(cfg.params)
        enabled = cfg.enabled
        weight = cfg.weight
        if provider_overrides and cfg.provider_id in provider_overrides:
            override = provider_overrides[cfg.provider_id]
            enabled = bool(override.get("enabled", enabled))
            weight = float(override.get("weight", weight))
            params.update(
                {key: value for key, value in override.items() if key not in {"enabled", "weight"}}
            )
        if not enabled:
            continue
        providers.append(
            instantiate_provider(
                cfg.model_copy(update={"enabled": enabled, "weight": weight, "params": params})
            )
        )
    return providers


def synthetic_revision_from_trial(
    trial: dict[str, Any], *, label: str = "optimizer_trial"
) -> ConfigRevision:
    payload = json.dumps(trial, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    fill_model = load_default_fill_model(resolve_config_dir())
    return ConfigRevision(
        revision_id=f"rev_opt_{digest}",
        created_at=datetime.now(UTC),
        engine_config_hash=digest,
        features_config_hash="optimizer",
        providers_config_hash=digest,
        fill_model_id=fill_model.model_id,
        risk_limits_hash=digest,
        label=label,
        config_bundle={"trial": trial},
    )
