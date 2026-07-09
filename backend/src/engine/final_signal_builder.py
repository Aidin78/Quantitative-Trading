from __future__ import annotations

import uuid

from src.core.contracts.context import MarketContext
from src.core.contracts.signal import FinalSignal, StrategySignal
from src.core.contracts.state import StateSnapshot
from src.engine.models import AggregatorSuccess


class FinalSignalBuilder:
    def build(
        self,
        aggregated: AggregatorSuccess,
        signals: list[StrategySignal],
        context: MarketContext,
        snapshot: StateSnapshot,
        *,
        decision_time,
        revision_id: str | None = None,
    ) -> FinalSignal:
        winners = [s for s in signals if s.provider_id in aggregated.weights]
        entry = context.current_price
        stop_loss, take_profit = self._merge_levels(
            aggregated.side,
            winners,
            entry,
            aggregated.weights,
        )
        risk_reward = self._risk_reward(aggregated.side, entry, stop_loss, take_profit)

        return FinalSignal(
            id=f"sig_{uuid.uuid4().hex[:12]}",
            symbol=context.symbol,
            side=aggregated.side,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=aggregated.confidence,
            risk_reward=risk_reward,
            timeframe=context.timeframe,
            event_time=context.event_time,
            decision_time=decision_time,
            contributing_providers=tuple(aggregated.weights.keys()),
            state_snapshot_id=snapshot.snapshot_id,
            revision_id=revision_id,
        )

    def _merge_levels(
        self,
        side: str,
        winners: list[StrategySignal],
        entry: float,
        weights: dict[str, float],
    ) -> tuple[float, float]:
        stops = [s for s in winners if s.stop_loss is not None]
        targets = [s for s in winners if s.take_profit is not None]

        def weighted_avg(values: list[tuple[float, float]]) -> float | None:
            if not values:
                return None
            total_w = sum(weight for _, weight in values)
            if total_w <= 0:
                return sum(level for level, _ in values) / len(values)
            return sum(level * weight for level, weight in values) / total_w

        if side == "BUY":
            stop_levels = [(float(s.stop_loss), weights.get(s.provider_id, 1.0)) for s in stops]
            target_levels = [
                (float(s.take_profit), weights.get(s.provider_id, 1.0)) for s in targets
            ]
            stop_loss = weighted_avg(stop_levels) if stop_levels else entry * 0.99
            take_profit = weighted_avg(target_levels) if target_levels else entry * 1.02
        else:
            stop_levels = [(float(s.stop_loss), weights.get(s.provider_id, 1.0)) for s in stops]
            target_levels = [
                (float(s.take_profit), weights.get(s.provider_id, 1.0)) for s in targets
            ]
            stop_loss = weighted_avg(stop_levels) if stop_levels else entry * 1.01
            take_profit = weighted_avg(target_levels) if target_levels else entry * 0.98

        return stop_loss, take_profit

    @staticmethod
    def _risk_reward(side: str, entry: float, stop_loss: float, take_profit: float) -> float:
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        if risk == 0:
            return 0.0
        return round(reward / risk, 4)
