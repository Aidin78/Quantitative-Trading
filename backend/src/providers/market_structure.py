from __future__ import annotations

from typing import Literal

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import RationaleFactor
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _market_structure_confidence(*, bias: float, bos: float, atr: float, close: float) -> float:
    structure_strength = min(abs(bias), 1.0)
    bos_strength = min(abs(bos), 1.0)
    atr_safe = max(atr, 1e-9)
    distance = abs(close) / atr_safe * 0.01 * bos_strength
    return _clamp(
        0.55 + 0.15 * structure_strength + 0.2 * bos_strength + 0.1 * distance, 0.55, 0.95
    )


class MarketStructureProvider(BaseSignalProvider):
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        bias = float(features.indicators.get("ms_bias", 0.0))
        bos = float(features.indicators.get("ms_bos", 0.0))
        close = float(features.close)

        min_confidence = float(self.params.get("min_confidence", 0.6))
        require_bos = bool(self.params.get("require_bos", True))
        require_trend = bool(self.params.get("require_trend", False))

        bullish = bias > 0 and (not require_bos or bos > 0)
        bearish = bias < 0 and (not require_bos or bos < 0)

        side: Literal["BUY", "SELL", "HOLD"]
        direction: Literal["bullish", "bearish", "neutral"]
        if bullish and not bearish:
            side = "BUY"
            direction = "bullish"
            summary = "Market structure bullish — HH/HL"
            if bos > 0:
                summary = f"{summary} with bullish BOS"
        elif bearish and not bullish:
            side = "SELL"
            direction = "bearish"
            summary = "Market structure bearish — LH/LL"
            if bos < 0:
                summary = f"{summary} with bearish BOS"
        else:
            side = "HOLD"
            direction = "neutral"
            if bias == 0:
                summary = "Neutral/choppy market structure"
            elif require_bos and bos == 0:
                summary = "Structure bias without BOS confirmation"
            else:
                summary = "No market structure signal"

        confidence = _market_structure_confidence(bias=bias, bos=bos, atr=context.atr, close=close)

        if require_trend:
            if side == "BUY" and context.trend == "DOWN":
                side = "HOLD"
                summary = f"{summary} — trend filter"
            if side == "SELL" and context.trend == "UP":
                side = "HOLD"
                summary = f"{summary} — trend filter"

        rationale = self._rationale(
            summary=summary,
            feature_refs={
                "close": close,
                "ms_bias": bias,
                "ms_bos": bos,
            },
            factors=(
                RationaleFactor(
                    name="market_structure",
                    weight=1.0,
                    direction=direction,
                    evidence=f"bias={bias:.0f}, bos={bos:.0f}, close={close:.2f}",
                ),
            ),
        )

        if side == "HOLD" or confidence < min_confidence:
            hold_summary = summary if side == "HOLD" else f"{summary} — below min confidence"
            return self._build_signal(
                features=features,
                context=context,
                side="HOLD",
                confidence=confidence if side == "HOLD" else min_confidence - 0.01,
                rationale=self._rationale(
                    summary=hold_summary,
                    feature_refs={
                        "close": close,
                        "ms_bias": bias,
                        "ms_bos": bos,
                    },
                    factors=rationale.factors,
                ),
            )

        stop_loss, take_profit = self._atr_stops(context, side)
        return self._build_signal(
            features=features,
            context=context,
            side=side,
            confidence=confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
            rationale=rationale,
        )
