from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class AggregationConfig(BaseModel, frozen=True):
    min_agreeing_providers: int = Field(ge=1)
    method: Literal["weighted_majority", "majority", "unanimous"] = "weighted_majority"


class FilterConfig(BaseModel, frozen=True):
    min_atr_pct: float = Field(ge=0.0)
    allowed_sessions: tuple[str, ...]


class RiskConfig(BaseModel, frozen=True):
    max_daily_drawdown_pct: float = Field(ge=0.0)
    max_signals_per_day: int = Field(ge=1)
    min_confidence: float = Field(ge=0.0, le=1.0)
    min_risk_reward: float = Field(ge=0.0)
    max_open_positions: int = Field(ge=0)
    max_exposure_pct: float = Field(ge=0.0)


class EngineConfig(BaseModel, frozen=True):
    aggregation: AggregationConfig
    filter: FilterConfig
    risk: RiskConfig


def resolve_config_dir() -> Path:
    from src.core.settings import resolve_config_dir as _resolve

    return _resolve()


@lru_cache
def load_engine_config(config_dir: Path | None = None) -> EngineConfig:
    base = config_dir or resolve_config_dir()
    path = base / "engine.yaml"
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    engine = raw["engine"]
    return EngineConfig(
        aggregation=AggregationConfig(**engine["aggregation"]),
        filter=FilterConfig(
            min_atr_pct=engine["filter"]["min_atr_pct"],
            allowed_sessions=tuple(engine["filter"]["allowed_sessions"]),
        ),
        risk=RiskConfig(**engine["risk"]),
    )
