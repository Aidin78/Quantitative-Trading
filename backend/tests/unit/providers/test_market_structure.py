from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.providers.base import ProviderConfig
from src.providers.market_structure import MarketStructureProvider
from tests.unit.providers.conftest import make_feature_set


def _ms_features(
    *,
    bias: float = 1.0,
    bos: float = 1.0,
) -> dict[str, float]:
    return {
        "ms_bias": bias,
        "ms_bos": bos,
    }


def test_bullish_structure_with_bos_emits_buy(context) -> None:
    provider = MarketStructureProvider(
        ProviderConfig(provider_id="market_structure", params={"min_confidence": 0.55})
    )
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_ms_features()),
        context,
    )
    assert signal.side == "BUY"
    assert signal.confidence >= 0.55
    assert signal.stop_loss is not None
    assert signal.take_profit is not None


def test_bearish_structure_with_bos_emits_sell(context) -> None:
    provider = MarketStructureProvider(
        ProviderConfig(provider_id="market_structure", params={"min_confidence": 0.55})
    )
    down_context = MarketContext(
        symbol=context.symbol,
        timeframe=context.timeframe,
        current_price=66800.0,
        trend="DOWN",
        volatility=context.volatility,
        atr=context.atr,
        atr_pct=context.atr_pct,
        session=context.session,
        event_time=context.event_time,
    )
    signal = provider.analyze(
        make_feature_set(
            close=66800.0,
            indicators=_ms_features(bias=-1.0, bos=-1.0),
        ),
        down_context,
    )
    assert signal.side == "SELL"
    assert signal.confidence >= 0.55


def test_neutral_bias_emits_hold(context) -> None:
    provider = MarketStructureProvider(ProviderConfig(provider_id="market_structure"))
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_ms_features(bias=0.0, bos=0.0)),
        context,
    )
    assert signal.side == "HOLD"


def test_require_bos_blocks_bias_without_break(context) -> None:
    provider = MarketStructureProvider(
        ProviderConfig(
            provider_id="market_structure",
            params={"require_bos": True},
        )
    )
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_ms_features(bias=1.0, bos=0.0)),
        context,
    )
    assert signal.side == "HOLD"


def test_require_bos_disabled_allows_bias_only(context) -> None:
    provider = MarketStructureProvider(
        ProviderConfig(
            provider_id="market_structure",
            params={"require_bos": False, "min_confidence": 0.55},
        )
    )
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_ms_features(bias=1.0, bos=0.0)),
        context,
    )
    assert signal.side == "BUY"


def test_require_trend_blocks_buy_in_down(context) -> None:
    provider = MarketStructureProvider(
        ProviderConfig(
            provider_id="market_structure",
            params={"require_trend": True},
        )
    )
    down_context = MarketContext(
        symbol=context.symbol,
        timeframe=context.timeframe,
        current_price=context.current_price,
        trend="DOWN",
        volatility=context.volatility,
        atr=context.atr,
        atr_pct=context.atr_pct,
        session=context.session,
        event_time=context.event_time,
    )
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_ms_features()),
        down_context,
    )
    assert signal.side == "HOLD"


def test_below_min_confidence_emits_hold(context) -> None:
    provider = MarketStructureProvider(
        ProviderConfig(
            provider_id="market_structure",
            params={"min_confidence": 0.99},
        )
    )
    signal = provider.analyze(
        make_feature_set(close=67000.0, indicators=_ms_features()),
        context,
    )
    assert signal.side == "HOLD"
