from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import ProviderRationale, RationaleFactor
from src.core.contracts.signal import StrategySignal


class ProviderConfig(BaseModel, frozen=True):
    provider_id: str
    version: str = "v1"
    enabled: bool = True
    weight: float = Field(default=1.0, ge=0.0)
    params: dict[str, Any] = Field(default_factory=dict)


class BaseSignalProvider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    @property
    def provider_id(self) -> str:
        return self._config.provider_id

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def weight(self) -> float:
        return self._config.weight

    @property
    def params(self) -> dict[str, Any]:
        return self._config.params

    @abstractmethod
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal: ...

    def _build_signal(
        self,
        *,
        features: FeatureSet,
        context: MarketContext,
        side: Literal["BUY", "SELL", "HOLD"],
        confidence: float,
        rationale: ProviderRationale,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> StrategySignal:
        return StrategySignal(
            provider_id=self.provider_id,
            symbol=features.symbol,
            side=side,
            confidence=confidence,
            rationale=rationale,
            feature_set_id=features.feature_set_id,
            entry_price=context.current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timeframe=features.timeframe,
            event_time=features.event_time,
        )

    def _atr_stops(
        self,
        context: MarketContext,
        side: Literal["BUY", "SELL"],
        *,
        sl_atr_mult: float = 1.5,
        tp_atr_mult: float = 3.0,
    ) -> tuple[float, float]:
        price = context.current_price
        atr = context.atr
        if side == "BUY":
            return price - sl_atr_mult * atr, price + tp_atr_mult * atr
        return price + sl_atr_mult * atr, price - tp_atr_mult * atr

    def _rationale(
        self,
        *,
        summary: str,
        feature_refs: dict[str, float] | None = None,
        factors: tuple[RationaleFactor, ...] = (),
    ) -> ProviderRationale:
        return ProviderRationale(
            summary=summary,
            factors=factors,
            feature_refs=feature_refs or {},
            metadata={"weight": self.weight},
        )
