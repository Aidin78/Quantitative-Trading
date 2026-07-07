from __future__ import annotations

from typing import Literal

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import RationaleFactor
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider


class RsiDivergenceProvider(BaseSignalProvider):
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        rsi = features.indicators.get("rsi_14", 50.0)
        oversold = float(self.params.get("oversold", 30))
        overbought = float(self.params.get("overbought", 70))
        min_confidence = float(self.params.get("min_confidence", 0.65))

        side: Literal["BUY", "SELL", "HOLD"]
        direction: Literal["bullish", "bearish", "neutral"]
        if rsi < oversold:
            side = "BUY"
            direction = "bullish"
            confidence = 0.72
            summary = f"RSI oversold ({rsi:.1f})"
        elif rsi > overbought:
            side = "SELL"
            direction = "bearish"
            confidence = 0.72
            summary = f"RSI overbought ({rsi:.1f})"
        else:
            side = "HOLD"
            direction = "neutral"
            confidence = 0.5
            summary = f"RSI neutral ({rsi:.1f})"

        if side != "HOLD" and confidence < min_confidence:
            side = "HOLD"
            summary = f"{summary} — below min confidence"

        rationale = self._rationale(
            summary=summary,
            feature_refs={"rsi_14": rsi},
            factors=(
                RationaleFactor(
                    name="rsi_14",
                    weight=1.0,
                    direction=direction,
                    evidence=f"rsi={rsi:.1f}, oversold={oversold}, overbought={overbought}",
                ),
            ),
        )

        if side == "HOLD":
            return self._build_signal(
                features=features,
                context=context,
                side="HOLD",
                confidence=confidence,
                rationale=rationale,
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
