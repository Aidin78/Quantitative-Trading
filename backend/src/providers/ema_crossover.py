from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import RationaleFactor
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider


def _ema_confidence(
    features: FeatureSet,
    context: MarketContext,
    *,
    bullish: bool,
    bearish: bool,
) -> float:
    if not bullish and not bearish:
        return 0.5
    ema_fast = float(features.indicators.get("ema_12", context.current_price))
    ema_slow = float(features.indicators.get("ema_26", context.current_price))
    spread = ema_fast - ema_slow
    atr = max(context.atr, 1e-9)
    spread_ratio = abs(spread) / atr
    return min(0.95, max(0.55, 0.55 + 0.12 * spread_ratio))


class EmaCrossoverProvider(BaseSignalProvider):
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        bullish = bool(features.flags.get("ema_cross_bullish", False))
        bearish = bool(features.flags.get("ema_cross_bearish", False))
        min_confidence = float(self.params.get("min_confidence", 0.6))
        require_trend = bool(self.params.get("require_trend", True))
        confidence = _ema_confidence(features, context, bullish=bullish, bearish=bearish)

        side = "HOLD"
        if bullish and not bearish:
            side = "BUY"
        elif bearish and not bullish:
            side = "SELL"

        if require_trend:
            if side == "BUY" and context.trend == "DOWN":
                side = "HOLD"
                confidence = 0.5
            if side == "SELL" and context.trend == "UP":
                side = "HOLD"
                confidence = 0.5

        if side == "HOLD" or confidence < min_confidence:
            summary = "No EMA cross"
            if side != "HOLD":
                summary = "EMA cross below min confidence"
            return self._build_signal(
                features=features,
                context=context,
                side="HOLD",
                confidence=confidence if side == "HOLD" else min_confidence - 0.01,
                rationale=self._rationale(
                    summary=summary,
                    feature_refs={
                        "ema_cross_bullish": 1.0 if bullish else 0.0,
                        "ema_cross_bearish": 1.0 if bearish else 0.0,
                    },
                    factors=(
                        RationaleFactor(
                            name="ema_cross",
                            weight=1.0,
                            direction="bullish" if bullish else "bearish" if bearish else "neutral",
                            evidence="ema fast vs slow cross",
                        ),
                    ),
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
            rationale=self._rationale(
                summary=f"EMA cross {side.lower()}",
                feature_refs={
                    "ema_cross_bullish": 1.0 if bullish else 0.0,
                    "ema_cross_bearish": 1.0 if bearish else 0.0,
                },
                factors=(
                    RationaleFactor(
                        name="ema_cross",
                        weight=1.0,
                        direction="bullish" if side == "BUY" else "bearish",
                        evidence="ema_12 vs ema_26 cross",
                    ),
                ),
            ),
        )
