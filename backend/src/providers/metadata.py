from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ParamField:
    key: str
    label: str
    type: Literal["float", "int", "bool"]
    description: str
    min: float | None = None
    max: float | None = None
    step: float | None = None


@dataclass(frozen=True)
class ProviderMetadata:
    summary: str
    rules: tuple[str, ...]
    default_config: dict[str, Any]
    param_fields: tuple[ParamField, ...]
    required_features: tuple[str, ...]


_SHARED_STOPS = (
    ParamField(
        key="min_confidence",
        label="Min confidence",
        type="float",
        description="Minimum computed confidence before emitting BUY/SELL.",
        min=0.0,
        max=1.0,
        step=0.01,
    ),
    ParamField(
        key="sl_atr_mult",
        label="Stop-loss ATR mult",
        type="float",
        description="Stop distance as a multiple of ATR.",
        min=0.1,
        step=0.1,
    ),
    ParamField(
        key="tp_atr_mult",
        label="Take-profit ATR mult",
        type="float",
        description="Take-profit distance as a multiple of ATR.",
        min=0.1,
        step=0.1,
    ),
)


PROVIDER_METADATA: dict[str, ProviderMetadata] = {
    "ema_crossover": ProviderMetadata(
        summary="EMA fast/slow cross with optional trend filter.",
        rules=(
            "BUY when ema_cross_bullish flag is set (ema_12 > ema_26).",
            "SELL when ema_cross_bearish flag is set (ema_12 < ema_26).",
            "Confidence scales with EMA spread relative to ATR.",
            "If require_trend: block BUY in DOWN trend and SELL in UP trend.",
            "Below min_confidence → HOLD.",
        ),
        default_config={
            "enabled": True,
            "weight": 1.0,
            "params": {
                "min_confidence": 0.6,
                "sl_atr_mult": 1.5,
                "tp_atr_mult": 4.0,
                "require_trend": True,
            },
        },
        param_fields=_SHARED_STOPS
        + (
            ParamField(
                key="require_trend",
                label="Require trend alignment",
                type="bool",
                description="Only BUY in UP trend and SELL in DOWN trend.",
            ),
        ),
        required_features=("ema_cross_bullish", "ema_cross_bearish"),
    ),
    "rsi_divergence": ProviderMetadata(
        summary="RSI threshold strategy (oversold/overbought levels).",
        rules=(
            "BUY when RSI < oversold threshold.",
            "SELL when RSI > overbought threshold.",
            "Otherwise HOLD.",
            "If avoid_high_vol and volatility is HIGH → force HOLD.",
            "Below min_confidence → HOLD.",
        ),
        default_config={
            "enabled": True,
            "weight": 1.0,
            "params": {
                "min_confidence": 0.6,
                "sl_atr_mult": 1.5,
                "tp_atr_mult": 4.0,
                "oversold": 30.0,
                "overbought": 70.0,
                "avoid_high_vol": True,
            },
        },
        param_fields=_SHARED_STOPS
        + (
            ParamField(
                key="oversold",
                label="Oversold",
                type="float",
                description="RSI below this level triggers BUY.",
                min=0.0,
                max=100.0,
                step=1.0,
            ),
            ParamField(
                key="overbought",
                label="Overbought",
                type="float",
                description="RSI above this level triggers SELL.",
                min=0.0,
                max=100.0,
                step=1.0,
            ),
            ParamField(
                key="avoid_high_vol",
                label="Avoid high volatility",
                type="bool",
                description="Suppress entries when market volatility is HIGH.",
            ),
        ),
        required_features=("rsi_14",),
    ),
    "macd_momentum": ProviderMetadata(
        summary="MACD histogram momentum with optional signal-line alignment.",
        rules=(
            "BUY when histogram > 0 and histogram_slope > min_histogram_slope.",
            "SELL when histogram < 0 and histogram_slope < -min_histogram_slope.",
            "If require_signal_align: MACD line must agree (line > signal for BUY).",
            "If require_trend: block BUY in DOWN and SELL in UP.",
            "Confidence from histogram and slope strength normalized by ATR.",
            "Below min_confidence → HOLD.",
        ),
        default_config={
            "enabled": True,
            "weight": 1.0,
            "params": {
                "min_confidence": 0.6,
                "sl_atr_mult": 1.5,
                "tp_atr_mult": 4.0,
                "require_signal_align": True,
                "min_histogram_slope": 0.0,
                "require_trend": False,
            },
        },
        param_fields=_SHARED_STOPS
        + (
            ParamField(
                key="require_signal_align",
                label="Require signal alignment",
                type="bool",
                description="MACD line must agree with histogram direction.",
            ),
            ParamField(
                key="min_histogram_slope",
                label="Min histogram slope",
                type="float",
                description="Minimum absolute histogram slope for entry.",
                step=0.0001,
            ),
            ParamField(
                key="require_trend",
                label="Require trend alignment",
                type="bool",
                description="Only BUY in UP trend and SELL in DOWN trend.",
            ),
        ),
        required_features=(
            "macd",
            "macd_signal",
            "macd_histogram",
            "macd_histogram_slope",
        ),
    ),
}


def get_provider_metadata(provider_id: str) -> ProviderMetadata | None:
    return PROVIDER_METADATA.get(provider_id)


def metadata_to_dict(meta: ProviderMetadata) -> dict[str, Any]:
    return {
        "summary": meta.summary,
        "rules": list(meta.rules),
        "default_config": meta.default_config,
        "param_fields": [
            {
                "key": field.key,
                "label": field.label,
                "type": field.type,
                "description": field.description,
                "min": field.min,
                "max": field.max,
                "step": field.step,
            }
            for field in meta.param_fields
        ],
        "required_features": list(meta.required_features),
    }
