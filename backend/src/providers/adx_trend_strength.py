from __future__ import annotations

from typing import Literal

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import RationaleFactor
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _adx_confidence(*, adx: float, di_spread: float) -> float:
    adx_strength = max(0.0, adx - 20.0) / 40.0
    spread_strength = min(di_spread / 20.0, 1.0)
    return _clamp(0.55 + 0.2 * adx_strength + 0.15 * spread_strength, 0.55, 0.95)


class AdxTrendStrengthProvider(BaseSignalProvider):
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        adx = float(features.indicators.get("adx_14", 0.0))
        plus_di = float(features.indicators.get("plus_di_14", 0.0))
        minus_di = float(features.indicators.get("minus_di_14", 0.0))

        min_confidence = float(self.params.get("min_confidence", 0.6))
        min_adx = float(self.params.get("min_adx", 25.0))
        min_di_spread = float(self.params.get("min_di_spread", 5.0))
        require_trend = bool(self.params.get("require_trend", False))

        di_spread = abs(plus_di - minus_di)
        strong_trend = adx >= min_adx and di_spread >= min_di_spread

        bullish = strong_trend and plus_di > minus_di
        bearish = strong_trend and minus_di > plus_di

        side: Literal["BUY", "SELL", "HOLD"]
        direction: Literal["bullish", "bearish", "neutral"]
        if bullish and not bearish:
            side = "BUY"
            direction = "bullish"
            summary = "ADX trend strength bullish"
        elif bearish and not bullish:
            side = "SELL"
            direction = "bearish"
            summary = "ADX trend strength bearish"
        else:
            side = "HOLD"
            direction = "neutral"
            if adx < min_adx:
                summary = "ADX below minimum — weak trend"
            elif di_spread < min_di_spread:
                summary = "DI spread too narrow — no conviction"
            else:
                summary = "No ADX trend signal"

        confidence = _adx_confidence(adx=adx, di_spread=di_spread)

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
                "adx_14": adx,
                "plus_di_14": plus_di,
                "minus_di_14": minus_di,
            },
            factors=(
                RationaleFactor(
                    name="adx_trend_strength",
                    weight=1.0,
                    direction=direction,
                    evidence=(
                        f"adx={adx:.2f}, plus_di={plus_di:.2f}, "
                        f"minus_di={minus_di:.2f}, spread={di_spread:.2f}"
                    ),
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
                        "adx_14": adx,
                        "plus_di_14": plus_di,
                        "minus_di_14": minus_di,
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
