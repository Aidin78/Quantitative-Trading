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
    "adx_trend_strength": ProviderMetadata(
        summary="ADX trend strength with directional DI confirmation.",
        rules=(
            "BUY when ADX >= min_adx and plus_di > minus_di with spread >= min_di_spread.",
            "SELL when ADX >= min_adx and minus_di > plus_di with spread >= min_di_spread.",
            "ADX below min_adx or narrow DI spread → HOLD (weak/choppy market).",
            "If require_trend: block BUY in DOWN and SELL in UP.",
            "Confidence scales with ADX level and DI spread.",
            "Below min_confidence → HOLD.",
        ),
        default_config={
            "enabled": False,
            "weight": 1.0,
            "params": {
                "min_confidence": 0.6,
                "sl_atr_mult": 1.5,
                "tp_atr_mult": 4.0,
                "min_adx": 25.0,
                "min_di_spread": 5.0,
                "require_trend": False,
            },
        },
        param_fields=_SHARED_STOPS
        + (
            ParamField(
                key="min_adx",
                label="Min ADX",
                type="float",
                description="Minimum ADX for a strong trend.",
                min=0.0,
                max=100.0,
                step=1.0,
            ),
            ParamField(
                key="min_di_spread",
                label="Min DI spread",
                type="float",
                description="Minimum |+DI - -DI| for directional conviction.",
                min=0.0,
                max=100.0,
                step=1.0,
            ),
            ParamField(
                key="require_trend",
                label="Require trend alignment",
                type="bool",
                description="Only BUY in UP trend and SELL in DOWN trend.",
            ),
        ),
        required_features=("adx_14", "plus_di_14", "minus_di_14"),
    ),
    "bollinger_reversion": ProviderMetadata(
        summary="Mean reversion when price touches Bollinger upper or lower bands.",
        rules=(
            "BUY when close <= bb_lower (oversold at lower band).",
            "SELL when close >= bb_upper (overbought at upper band).",
            "Price inside bands → HOLD.",
            "If avoid_high_vol: suppress entries when volatility is HIGH.",
            "If max_adx > 0: suppress entries when ADX exceeds threshold (strong trend).",
            "Confidence scales with penetration beyond the band relative to band width.",
            "Below min_confidence → HOLD.",
        ),
        default_config={
            "enabled": False,
            "weight": 1.0,
            "params": {
                "min_confidence": 0.6,
                "sl_atr_mult": 1.5,
                "tp_atr_mult": 4.0,
                "avoid_high_vol": True,
                "max_adx": 0.0,
            },
        },
        param_fields=_SHARED_STOPS
        + (
            ParamField(
                key="avoid_high_vol",
                label="Avoid high volatility",
                type="bool",
                description="Suppress entries when market volatility is HIGH.",
            ),
            ParamField(
                key="max_adx",
                label="Max ADX for reversion",
                type="float",
                description="Skip signals when ADX exceeds this (0 = disabled).",
                min=0.0,
                max=100.0,
                step=1.0,
            ),
        ),
        required_features=("bb_upper", "bb_lower", "bb_middle"),
    ),
    "supertrend_trend": ProviderMetadata(
        summary="SuperTrend trend-following: trade in the direction of the SuperTrend line.",
        rules=(
            "BUY when supertrend_direction > 0 (price above SuperTrend line).",
            "SELL when supertrend_direction < 0 (price below SuperTrend line).",
            "Neutral direction → HOLD.",
            "If require_trend: block BUY in DOWN and SELL in UP.",
            "Confidence scales with distance from SuperTrend line normalized by ATR.",
            "Below min_confidence → HOLD.",
        ),
        default_config={
            "enabled": False,
            "weight": 1.0,
            "params": {
                "min_confidence": 0.6,
                "sl_atr_mult": 1.5,
                "tp_atr_mult": 4.0,
                "require_trend": False,
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
        required_features=("supertrend", "supertrend_direction"),
    ),
    "volume_order_flow": ProviderMetadata(
        summary="Volume / order flow proxy via Chaikin Money Flow and relative volume (OHLCV).",
        rules=(
            "BUY when CMF >= min_cmf and volume_ratio >= min_volume_ratio (accumulation).",
            "SELL when CMF <= -min_cmf and volume_ratio >= min_volume_ratio (distribution).",
            "Weak CMF or low relative volume → HOLD.",
            "If require_price_align: BUY needs rising close; SELL needs falling close.",
            "Confidence scales with CMF strength and volume surge.",
            "Below min_confidence → HOLD.",
        ),
        default_config={
            "enabled": False,
            "weight": 1.0,
            "params": {
                "min_confidence": 0.5,
                "sl_atr_mult": 1.5,
                "tp_atr_mult": 4.0,
                "period": 20,
                "min_cmf": 0.05,
                "min_volume_ratio": 1.2,
                "require_price_align": True,
            },
        },
        param_fields=_SHARED_STOPS
        + (
            ParamField(
                key="period",
                label="Lookback period",
                type="int",
                description="Shared period for CMF and volume ratio.",
                min=2.0,
                max=100.0,
                step=1.0,
            ),
            ParamField(
                key="min_cmf",
                label="Min CMF",
                type="float",
                description="Minimum absolute Chaikin Money Flow for a directional signal.",
                min=0.0,
                max=1.0,
                step=0.01,
            ),
            ParamField(
                key="min_volume_ratio",
                label="Min volume ratio",
                type="float",
                description="Current volume vs SMA(volume) required for entry.",
                min=0.5,
                step=0.1,
            ),
            ParamField(
                key="require_price_align",
                label="Require price alignment",
                type="bool",
                description="BUY only on rising close; SELL only on falling close.",
            ),
        ),
        required_features=("cmf_20", "volume_ratio_20", "close_delta"),
    ),
    "market_structure": ProviderMetadata(
        summary=(
            "SMC-style market structure from swing pivots: "
            "HH/HL vs LH/LL and break of structure."
        ),
        rules=(
            "BUY when ms_bias > 0 (HH + HL bullish structure).",
            "SELL when ms_bias < 0 (LH + LL bearish structure).",
            "If require_bos: bias must align with ms_bos break of last swing.",
            "Neutral/choppy structure or missing BOS → HOLD.",
            "If require_trend: block BUY in DOWN and SELL in UP.",
            "Confidence scales with structure and BOS strength.",
            "Below min_confidence → HOLD.",
        ),
        default_config={
            "enabled": False,
            "weight": 1.0,
            "params": {
                "min_confidence": 0.6,
                "sl_atr_mult": 1.5,
                "tp_atr_mult": 4.0,
                "pivot_bars": 5,
                "require_bos": True,
                "require_trend": False,
            },
        },
        param_fields=_SHARED_STOPS
        + (
            ParamField(
                key="pivot_bars",
                label="Pivot bars",
                type="int",
                description="Bars on each side to confirm swing highs/lows.",
                min=2.0,
                max=20.0,
                step=1.0,
            ),
            ParamField(
                key="require_bos",
                label="Require BOS",
                type="bool",
                description="Only emit signals when break of structure confirms bias.",
            ),
            ParamField(
                key="require_trend",
                label="Require trend alignment",
                type="bool",
                description="Only BUY in UP trend and SELL in DOWN trend.",
            ),
        ),
        required_features=("ms_bias", "ms_bos"),
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
