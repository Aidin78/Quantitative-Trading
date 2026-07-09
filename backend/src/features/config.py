from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class IndicatorDef(BaseModel, frozen=True):
    name: str
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class FlagDef(BaseModel, frozen=True):
    name: str
    expr: str


class TrendContextConfig(BaseModel, frozen=True):
    method: Literal["ema_compare"] = "ema_compare"
    fast: str
    slow: str


class VolatilityContextConfig(BaseModel, frozen=True):
    method: Literal["atr_pct"] = "atr_pct"
    atr: str
    low: float = Field(ge=0.0)
    high: float = Field(ge=0.0)


class SessionContextConfig(BaseModel, frozen=True):
    timezone: Literal["UTC"] = "UTC"


class ContextConfig(BaseModel, frozen=True):
    trend: TrendContextConfig
    volatility: VolatilityContextConfig
    session: SessionContextConfig = SessionContextConfig()


class FeaturesConfig(BaseModel, frozen=True):
    version: str
    indicators: tuple[IndicatorDef, ...]
    flags: tuple[FlagDef, ...] = ()
    context: ContextConfig


def resolve_config_dir() -> Path:
    from src.core.settings import resolve_config_dir as _resolve

    return _resolve()


def compute_config_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@lru_cache
def load_features_config(config_dir: Path | None = None) -> tuple[FeaturesConfig, str]:
    base = config_dir or resolve_config_dir()
    path = base / "features.yaml"
    content = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(content)
    config = FeaturesConfig(
        version=raw["version"],
        indicators=tuple(IndicatorDef(**item) for item in raw["indicators"]),
        flags=tuple(FlagDef(**item) for item in raw.get("flags", [])),
        context=ContextConfig(**raw["context"]),
    )
    return config, compute_config_hash(content)
