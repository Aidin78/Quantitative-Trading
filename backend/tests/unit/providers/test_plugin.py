from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet
from src.core.contracts.rationale import ProviderRationale
from src.core.contracts.signal import StrategySignal
from src.providers.base import BaseSignalProvider, ProviderConfig
from src.providers.registry import register_provider


class _StubProvider(BaseSignalProvider):
    def analyze(self, features: FeatureSet, context: MarketContext) -> StrategySignal:
        return StrategySignal(
            provider_id=self.provider_id,
            symbol=features.symbol,
            side="HOLD",
            confidence=0.5,
            rationale=ProviderRationale(summary="stub"),
            feature_set_id=features.feature_set_id,
            entry_price=context.current_price,
            timeframe=features.timeframe,
            event_time=features.event_time,
        )


def test_third_provider_plugs_in_without_engine_changes() -> None:
    register_provider("stub_plugin", _StubProvider)
    provider = _StubProvider(ProviderConfig(provider_id="stub_plugin", weight=0.3))
    assert provider.provider_id == "stub_plugin"
    assert provider.weight == 0.3
    assert hasattr(provider, "analyze")
