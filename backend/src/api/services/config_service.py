from __future__ import annotations

import yaml

from src.engine.config import EngineConfig, load_engine_config, resolve_config_dir
from src.execution.config import load_validation_execution_config
from src.providers.config import load_provider_yaml
from src.providers.registry import discover_provider_configs


def read_engine_config() -> EngineConfig:
    return load_engine_config()


def write_engine_config(patch: dict) -> EngineConfig:
    config_dir = resolve_config_dir()
    path = config_dir / "engine.yaml"
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    engine = raw.setdefault("engine", {})
    for section in ("aggregation", "filter", "risk"):
        if section in patch:
            engine.setdefault(section, {}).update(patch[section])
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False)
    load_engine_config.cache_clear()
    return load_engine_config(config_dir)


def list_provider_configs() -> list[dict]:
    return [cfg.model_dump() for cfg in discover_provider_configs()]


def read_provider_config(provider_id: str) -> dict | None:
    for cfg in discover_provider_configs():
        if cfg.provider_id == provider_id:
            return cfg.model_dump()
    return None


def write_provider_config(provider_id: str, patch: dict) -> dict:
    config_dir = resolve_config_dir()
    path = config_dir / "providers" / f"{provider_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Provider config not found: {provider_id}")
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    for key in ("enabled", "weight", "version"):
        if key in patch:
            raw[key] = patch[key]
    if "params" in patch:
        raw.setdefault("params", {}).update(patch["params"])
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False)
    return load_provider_yaml(path).model_dump()


def reset_provider_config(provider_id: str) -> dict:
    from src.providers.metadata import get_provider_metadata

    meta = get_provider_metadata(provider_id)
    if meta is None:
        raise FileNotFoundError(f"No defaults for provider: {provider_id}")
    defaults = meta.default_config
    return write_provider_config(
        provider_id,
        {
            "enabled": defaults["enabled"],
            "weight": defaults["weight"],
            "params": dict(defaults["params"]),
        },
    )


def reset_all_provider_configs() -> list[dict]:
    from src.providers.metadata import get_provider_metadata

    results: list[dict] = []
    for cfg in discover_provider_configs():
        if get_provider_metadata(cfg.provider_id) is None:
            continue
        results.append(reset_provider_config(cfg.provider_id))
    return results


def apply_baseline_provider_setup() -> list[dict]:
    """Reset core providers to factory params and enable the baseline trio."""
    from src.providers.metadata import get_provider_metadata

    baseline_ids = ("ema_crossover", "rsi_divergence", "macd_momentum")
    results: list[dict] = []
    for provider_id in baseline_ids:
        meta = get_provider_metadata(provider_id)
        if meta is None:
            raise FileNotFoundError(f"No defaults for provider: {provider_id}")
        defaults = meta.default_config
        results.append(
            write_provider_config(
                provider_id,
                {
                    "enabled": True,
                    "weight": defaults["weight"],
                    "params": dict(defaults["params"]),
                },
            )
        )
    return results


def write_validation_settings(patch: dict) -> dict:
    config_dir = resolve_config_dir()
    path = config_dir / "settings.yaml"
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    validation = raw.setdefault("validation", {})
    for key in ("max_bars_in_trade", "risk_pct_per_trade"):
        if key in patch:
            validation[key] = patch[key]
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False)
    load_validation_execution_config.cache_clear()
    from src.core.settings import load_app_yaml_config

    load_app_yaml_config.cache_clear()
    return validation


def write_features_config(
    *,
    ema_fast: int,
    ema_slow: int,
    rsi_period: int,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal_period: int = 9,
    adx_period: int = 14,
    bb_period: int = 20,
    bb_std: float = 2.0,
    st_period: int = 10,
    st_multiplier: float = 3.0,
    vol_period: int = 20,
) -> dict:
    from src.features.config import load_features_config

    config_dir = resolve_config_dir()
    path = config_dir / "features.yaml"
    macd_names = {"macd", "macd_signal", "macd_histogram", "macd_histogram_slope"}
    adx_names = {"adx_14", "plus_di_14", "minus_di_14"}
    bb_names = {"bb_upper", "bb_lower", "bb_middle"}
    st_names = {"supertrend", "supertrend_direction"}
    vol_names = {"cmf_20", "volume_ratio_20"}
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    for indicator in raw.get("indicators", []):
        if indicator.get("name") == "ema_12":
            indicator.setdefault("params", {})["period"] = ema_fast
        elif indicator.get("name") == "ema_26":
            indicator.setdefault("params", {})["period"] = ema_slow
        elif indicator.get("name") == "rsi_14":
            indicator.setdefault("params", {})["period"] = rsi_period
        elif indicator.get("name") in macd_names:
            params = indicator.setdefault("params", {})
            params["fast"] = macd_fast
            params["slow"] = macd_slow
            params["signal"] = macd_signal_period
        elif indicator.get("name") in adx_names:
            indicator.setdefault("params", {})["period"] = adx_period
        elif indicator.get("name") in bb_names:
            params = indicator.setdefault("params", {})
            params["period"] = bb_period
            params["std"] = bb_std
        elif indicator.get("name") in st_names:
            params = indicator.setdefault("params", {})
            params["period"] = st_period
            params["multiplier"] = st_multiplier
        elif indicator.get("name") in vol_names:
            indicator.setdefault("params", {})["period"] = vol_period
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False)
    load_features_config.cache_clear()
    return {
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
    }
