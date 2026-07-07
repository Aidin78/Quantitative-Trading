from __future__ import annotations

import yaml

from src.engine.config import EngineConfig, load_engine_config, resolve_config_dir
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
    for key in ("enabled", "weight", "params", "version"):
        if key in patch:
            raw[key] = patch[key]
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False)
    return load_provider_yaml(path).model_dump()
