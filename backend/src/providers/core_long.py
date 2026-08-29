from __future__ import annotations

from typing import Literal

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import RationaleFactor
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider

_MIN_CONF = 0.5


class CoreLongProvider(BaseSignalProvider):
    """Trend-regime gate for a risk-managed long crypto core.

    Not a directional edge — every one of those was rejected (see
    ``docs/development/*-findings.md``). This harvests the documented trend +
    vol-targeting risk premium: hold beta while the market is in an uptrend
    regime (``close > SMA(N)``), step aside otherwise. Validated statistically
    in ``docs/development/managed-long-core-findings.md`` (SMA200 gate cuts BTC
    max drawdown 83%→~42%, ETH 94%→~46%, raises Calmar ~50%).

    Emits ``BUY`` (high, fixed confidence) while ``current_price >
    features.indicators[sma_indicator]``; ``HOLD`` otherwise. It does **not**
    compute the SMA — that is ``FeatureBuilder``'s job (``sma_200`` in
    ``config/features.yaml``).

    Two pieces of the full strategy live outside this provider and are
    deliberately not implemented here:

    1. **Exit-to-flat on regime-off.** The engine closes a long only on an
       opposing ``SELL`` decision, which would also open a short — the
       research strategy goes to *cash*, not short. Set ``regime_off_side:
       SELL`` only on an engine configured to not open the resulting short
       (long-only mode); the default ``HOLD`` is safe but relies on some
       other exit (a wide ``max_bars_in_trade``, a separate risk gate, or a
       future long-only execution flag).
    2. **Volatility-targeted sizing.** ``w = target_vol / realized_vol``
       belongs in the RiskManager / execution sizing layer, not in a
       SignalProvider (providers emit an opinion + confidence, never a size).
    """

    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        sma_name = str(self.params.get("sma_indicator", "sma_200"))
        confidence = float(self.params.get("confidence", 0.9))
        min_confidence = float(self.params.get("min_confidence", 0.6))
        regime_off_side: Literal["HOLD", "SELL"] = self.params.get("regime_off_side", "HOLD")
        use_atr_stops = bool(self.params.get("use_atr_stops", True))

        sma = features.indicators.get(sma_name)
        price = context.current_price

        if sma is None:
            return self._hold(
                features,
                context,
                summary=f"{sma_name} not available — insufficient history for regime gate",
                sma_name=sma_name,
                sma_value=0.0,
                price=price,
            )

        sma = float(sma)
        regime_on = price > sma

        if regime_on:
            side: Literal["BUY", "SELL", "HOLD"] = "BUY"
            summary = f"Uptrend regime — price {price:.2f} > {sma_name} {sma:.2f}"
            direction = "bullish"
        else:
            side = regime_off_side
            summary = f"Risk-off — price {price:.2f} <= {sma_name} {sma:.2f}"
            direction = "bearish" if side == "SELL" else "neutral"

        conf = confidence if side != "HOLD" else _MIN_CONF
        regime_label = "on" if regime_on else "off"
        factors = (
            RationaleFactor(
                name="trend_regime",
                weight=1.0,
                direction=direction,
                evidence=f"price={price:.2f}, {sma_name}={sma:.2f}, regime={regime_label}",
            ),
        )
        feature_refs = {sma_name: sma, "price": price}

        if side == "HOLD" or conf < min_confidence:
            return self._hold(
                features,
                context,
                summary=summary if side == "HOLD" else f"{summary} — below min confidence",
                sma_name=sma_name,
                sma_value=sma,
                price=price,
                factors=factors,
            )

        stop_loss = take_profit = None
        if use_atr_stops:
            stop_loss, take_profit = self._atr_stops(context, side)

        return self._build_signal(
            features=features,
            context=context,
            side=side,
            confidence=conf,
            stop_loss=stop_loss,
            take_profit=take_profit,
            rationale=self._rationale(summary=summary, feature_refs=feature_refs, factors=factors),
        )

    def _hold(
        self,
        features: FeatureSet,
        context: MarketContext,
        *,
        summary: str,
        sma_name: str,
        sma_value: float,
        price: float,
        factors: tuple[RationaleFactor, ...] = (),
    ) -> StrategySignal:
        return self._build_signal(
            features=features,
            context=context,
            side="HOLD",
            confidence=_MIN_CONF,
            rationale=self._rationale(
                summary=summary,
                feature_refs={sma_name: sma_value, "price": price},
                factors=factors,
            ),
        )
