from __future__ import annotations

from src.providers.base import ProviderConfig
from src.providers.rsi_divergence import RsiDivergenceProvider
from tests.unit.providers.conftest import make_feature_set


def test_oversold_emits_buy(context) -> None:
    provider = RsiDivergenceProvider(
        ProviderConfig(
            provider_id="rsi_divergence",
            params={"oversold": 30, "overbought": 70, "min_confidence": 0.65},
        )
    )
    signal = provider.analyze(make_feature_set(indicators={"rsi_14": 25.0}), context)
    assert signal.side == "BUY"
    assert signal.rationale.feature_refs["rsi_14"] == 25.0
    assert signal.stop_loss is not None
    assert signal.take_profit is not None


def test_overbought_emits_sell(context) -> None:
    provider = RsiDivergenceProvider(ProviderConfig(provider_id="rsi_divergence"))
    signal = provider.analyze(make_feature_set(indicators={"rsi_14": 75.0}), context)
    assert signal.side == "SELL"
    assert signal.stop_loss > context.current_price
    assert signal.take_profit < context.current_price


def test_neutral_emits_hold(context) -> None:
    provider = RsiDivergenceProvider(ProviderConfig(provider_id="rsi_divergence"))
    signal = provider.analyze(make_feature_set(indicators={"rsi_14": 50.0}), context)
    assert signal.side == "HOLD"
    assert signal.stop_loss is None
    assert signal.take_profit is None
