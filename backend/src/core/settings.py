from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppInfo(BaseModel, frozen=True):
    name: str
    timezone: str


class ValidationDefaults(BaseModel, frozen=True):
    default_start: str
    min_trades: int = Field(ge=1)


class OptimizationDefaults(BaseModel, frozen=True):
    min_trades_test: int = Field(default=50, ge=0)
    min_trades_holdout: int = Field(default=20, ge=0)


class FillModelDefaults(BaseModel, frozen=True):
    default: str


class AppYamlConfig(BaseModel, frozen=True):
    app: AppInfo
    default_symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    validation: ValidationDefaults
    optimization: OptimizationDefaults = OptimizationDefaults()
    fill_models: FillModelDefaults


def _resolve_env_files() -> tuple[str, ...]:
    """Load .env from cwd, backend/, or monorepo root (first existing wins)."""
    here = Path(__file__).resolve()
    backend_root = here.parents[2]
    repo_root = here.parents[3]
    candidates = [
        Path.cwd() / ".env",
        backend_root / ".env",
        repo_root / ".env",
    ]
    seen: set[Path] = set()
    files: list[str] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        files.append(str(resolved))
    return tuple(files) if files else (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://trading:changeme@localhost:5432/trading"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60
    admin_username: str = "admin"
    admin_password: str = "changeme"
    cors_origins: str = "http://localhost:3000"
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    telegram_proxy_url: str = ""
    exchange_id: str = "binance"
    exchange_api_key: str = ""
    exchange_api_secret: str = ""
    config_dir: str | None = None
    environment: Literal["development", "staging", "production"] = "development"
    auth_required: bool = False


def resolve_config_dir(settings: Settings | None = None) -> Path:
    if config_dir := os.environ.get("CONFIG_DIR"):
        return Path(config_dir)
    if settings and settings.config_dir:
        return Path(settings.config_dir)
    # backend/src/core/settings.py -> repo root
    return Path(__file__).resolve().parents[3] / "config"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def load_app_yaml_config(config_dir: Path | None = None) -> AppYamlConfig:
    base = config_dir or resolve_config_dir(get_settings())
    path = base / "settings.yaml"
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AppYamlConfig(
        app=AppInfo(**raw["app"]),
        default_symbols=tuple(raw["default_symbols"]),
        timeframes=tuple(raw["timeframes"]),
        validation=ValidationDefaults(**raw["validation"]),
        optimization=OptimizationDefaults(**raw.get("optimization", {})),
        fill_models=FillModelDefaults(**raw["fill_models"]),
    )
