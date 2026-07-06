from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import ProviderRationale
from src.core.contracts.signal import StrategySignal


class MockEmaCrossoverProvider:
    provider_id = "ema_crossover"
    enabled = True
    weight = 1.0

    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        bullish = features.flags.get("ema_cross_bullish", False)
        side = "BUY" if bullish else "HOLD"
        confidence = 0.78 if bullish else 0.5
        return StrategySignal(
            provider_id=self.provider_id,
            symbol=features.symbol,
            side=side,
            confidence=confidence,
            rationale=ProviderRationale(
                summary="EMA cross bullish" if bullish else "No EMA cross",
                metadata={"weight": self.weight},
            ),
            feature_set_id=features.feature_set_id,
            entry_price=context.current_price,
            stop_loss=context.current_price * 0.99 if side == "BUY" else None,
            take_profit=context.current_price * 1.02 if side == "BUY" else None,
            timeframe=features.timeframe,
            event_time=features.event_time,
        )


class MockRsiDivergenceProvider:
    provider_id = "rsi_divergence"
    enabled = True
    weight = 1.0

    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        rsi = features.indicators.get("rsi_14", 50.0)
        if rsi < 30:
            side = "BUY"
            confidence = 0.72
            summary = f"RSI oversold ({rsi:.1f})"
        elif rsi > 70:
            side = "SELL"
            confidence = 0.72
            summary = f"RSI overbought ({rsi:.1f})"
        else:
            side = "HOLD"
            confidence = 0.5
            summary = f"RSI neutral ({rsi:.1f})"

        return StrategySignal(
            provider_id=self.provider_id,
            symbol=features.symbol,
            side=side,
            confidence=confidence,
            rationale=ProviderRationale(summary=summary, metadata={"weight": self.weight}),
            feature_set_id=features.feature_set_id,
            entry_price=context.current_price,
            stop_loss=context.current_price * 0.99 if side == "BUY" else 67500.0,
            take_profit=context.current_price * 1.02 if side == "BUY" else 65500.0,
            timeframe=features.timeframe,
            event_time=features.event_time,
        )
