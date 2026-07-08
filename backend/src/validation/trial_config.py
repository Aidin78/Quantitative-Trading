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
from src.providers.registry import discover_provider_configs, instantiate_provider


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
        }
    )
    return cfg.model_copy(update={"aggregation": aggregation, "risk": risk})


def build_provider_overrides(trial: dict[str, Any]) -> dict[str, dict[str, Any]]:
    min_confidence = float(trial.get("min_confidence", 0.65))
    sl_atr_mult = float(trial.get("sl_atr_mult", 1.5))
    tp_atr_mult = float(trial.get("tp_atr_mult", 3.0))
    shared = {
        "min_confidence": min_confidence,
        "sl_atr_mult": sl_atr_mult,
        "tp_atr_mult": tp_atr_mult,
    }
    return {
        "ema_crossover": dict(shared),
        "rsi_divergence": dict(shared),
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


def build_providers_from_overrides(
    provider_overrides: dict[str, dict[str, Any]] | None = None,
) -> list[SignalProvider]:
    providers: list[SignalProvider] = []
    for cfg in discover_provider_configs(resolve_config_dir()):
        if not cfg.enabled:
            continue
        params = dict(cfg.params)
        if provider_overrides and cfg.provider_id in provider_overrides:
            params.update(provider_overrides[cfg.provider_id])
        providers.append(instantiate_provider(cfg.model_copy(update={"params": params})))
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
