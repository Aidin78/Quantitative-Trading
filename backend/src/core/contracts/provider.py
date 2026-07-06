from typing import Protocol

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.signal import StrategySignal


class SignalProvider(Protocol):
    provider_id: str
    enabled: bool
    weight: float

    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal: ...
