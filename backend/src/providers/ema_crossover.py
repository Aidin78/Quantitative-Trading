from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import RationaleFactor
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider


class EmaCrossoverProvider(BaseSignalProvider):
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        bullish = features.flags.get("ema_cross_bullish", False)
        min_confidence = float(self.params.get("min_confidence", 0.6))
        confidence = 0.78 if bullish else 0.5

        if not bullish or confidence < min_confidence:
            return self._build_signal(
                features=features,
                context=context,
                side="HOLD",
                confidence=confidence if not bullish else min_confidence - 0.01,
                rationale=self._rationale(
                    summary="No EMA cross" if not bullish else "EMA cross below min confidence",
                    feature_refs={"ema_cross_bullish": 1.0 if bullish else 0.0},
                    factors=(
                        RationaleFactor(
                            name="ema_cross_bullish",
                            weight=1.0,
                            direction="bullish" if bullish else "neutral",
                            evidence="ema_12 > ema_26" if bullish else "ema_12 <= ema_26",
                        ),
                    ),
                ),
            )

        stop_loss, take_profit = self._atr_stops(context, "BUY")
        return self._build_signal(
            features=features,
            context=context,
            side="BUY",
            confidence=confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
            rationale=self._rationale(
                summary="EMA cross bullish",
                feature_refs={"ema_cross_bullish": 1.0},
                factors=(
                    RationaleFactor(
                        name="ema_cross_bullish",
                        weight=1.0,
                        direction="bullish",
                        evidence="ema_12 > ema_26",
                    ),
                ),
            ),
        )
