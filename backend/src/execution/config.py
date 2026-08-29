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
    #: Long-only mode: an approved SELL still closes an open long (handled
    #: upstream in ``evaluate_bar``), but never *opens* a short. Used by the
    #: managed long-core strategy, whose regime-off signal means "go to cash",
    #: not "go short". Default False keeps the symmetric long/short behaviour.
    long_only: bool = False
    #: Exposure-target sizing: when > 0, position notional is
    #: ``equity * exposure_pct_per_trade / 100`` regardless of stop distance
    #: (still capped by cash and ``max_exposure_pct``). This is the sizing
    #: model a "hold the core" strategy needs — fixed-fractional-*risk* sizing
    #: (the default, driven by stop distance) makes such a position negligibly
    #: small. 0 keeps the stop-distance risk model.
    exposure_pct_per_trade: float = Field(ge=0.0, le=100.0, default=0.0)


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
        long_only=bool(validation.get("long_only", False)),
        exposure_pct_per_trade=float(validation.get("exposure_pct_per_trade", 0.0)),
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
