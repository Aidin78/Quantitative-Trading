from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from src.core.contracts.execution import FillModel
from src.core.settings import get_settings, resolve_config_dir


class ValidationExecutionConfig(BaseModel, frozen=True):
    max_bars_in_trade: int = Field(ge=1, default=48)
    risk_pct_per_trade: float = Field(gt=0, le=10, default=1.0)


class FillModelSpec(BaseModel, frozen=True):
    slippage_bps: float = 0.0
    fee_bps: float = 0.0
    fill_at: str = "close"


@lru_cache
def load_validation_execution_config(config_dir: Path | None = None) -> ValidationExecutionConfig:
    base = config_dir or resolve_config_dir(get_settings())
    path = base / "settings.yaml"
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    validation = raw.get("validation", {})
    return ValidationExecutionConfig(
        max_bars_in_trade=validation.get("max_bars_in_trade", 48),
        risk_pct_per_trade=validation.get("risk_pct_per_trade", 1.0),
    )


@lru_cache
def load_default_fill_model(config_dir: Path | None = None) -> FillModel:
    base = config_dir or resolve_config_dir(get_settings())
    path = base / "settings.yaml"
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    fill_models = raw.get("fill_models", {})
    model_id = fill_models.get("default", "close_price_v1")
    specs = fill_models.get("models", {})
    spec = FillModelSpec(
        **specs.get(model_id, {"slippage_bps": 5, "fee_bps": 10, "fill_at": "close"})
    )
    return FillModel(
        model_id=model_id,
        slippage_bps=spec.slippage_bps,
        fee_bps=spec.fee_bps,
        fill_at=spec.fill_at,  # type: ignore[arg-type]
    )
