from __future__ import annotations

from pathlib import Path

import pytest

from src.core.settings import AppYamlConfig, Settings, get_settings, load_app_yaml_config


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    settings = get_settings()
    assert settings.jwt_secret == "test-secret"
    assert settings.environment == "staging"
    get_settings.cache_clear()


def test_load_app_yaml_config() -> None:
    load_app_yaml_config.cache_clear()
    config_dir = Path(__file__).resolve().parents[2] / "config"
    config = load_app_yaml_config(config_dir)
    assert isinstance(config, AppYamlConfig)
    assert config.app.name == "Quantitative Trading Platform"
    assert "BTC/USDT" in config.default_symbols
    assert config.validation.min_trades >= 1
    load_app_yaml_config.cache_clear()


def test_settings_defaults_without_env_file() -> None:
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql")
    assert settings.redis_url.startswith("redis://")
    assert settings.environment == "development"
