from __future__ import annotations

from src.core.contracts.context import MarketContext
from src.providers.base import ProviderConfig
from src.providers.macd_momentum import MacdMomentumProvider
from tests.unit.providers.conftest import make_feature_set


def _macd_features(
    *,
    macd: float = 0.0025,
    macd_signal: float = 0.0018,
    macd_histogram: float = 0.0007,
    macd_histogram_slope: float = 0.0002,
) -> dict[str, float]:
    return {
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_histogram": macd_histogram,
        "macd_histogram_slope": macd_histogram_slope,
    }


def test_bullish_momentum_emits_buy(context) -> None:
    provider = MacdMomentumProvider(
        ProviderConfig(provider_id="macd_momentum", params={"min_confidence": 0.55})
    )
    signal = provider.analyze(
        make_feature_set(indicators=_macd_features()),
        context,
    )
    assert signal.side == "BUY"
    assert signal.confidence >= 0.55
    assert signal.stop_loss is not None
    assert signal.take_profit is not None


def test_bearish_momentum_emits_sell(context) -> None:
    provider = MacdMomentumProvider(
        ProviderConfig(provider_id="macd_momentum", params={"min_confidence": 0.55})
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
        make_feature_set(
            indicators=_macd_features(
                macd=-0.0025,
                macd_signal=-0.0018,
                macd_histogram=-0.0007,
                macd_histogram_slope=-0.0002,
            )
        ),
        down_context,
    )
    assert signal.side == "SELL"
    assert signal.confidence >= 0.55


def test_opposing_slope_emits_hold(context) -> None:
    provider = MacdMomentumProvider(ProviderConfig(provider_id="macd_momentum"))
    signal = provider.analyze(
        make_feature_set(
            indicators=_macd_features(macd_histogram=0.0007, macd_histogram_slope=-0.0001)
        ),
        context,
    )
    assert signal.side == "HOLD"


def test_signal_align_violation_emits_hold(context) -> None:
    provider = MacdMomentumProvider(
        ProviderConfig(
            provider_id="macd_momentum",
            params={"require_signal_align": True},
        )
    )
    signal = provider.analyze(
        make_feature_set(
            indicators=_macd_features(
                macd=0.0010,
                macd_signal=0.0020,
                macd_histogram=0.0007,
                macd_histogram_slope=0.0002,
            )
        ),
        context,
    )
    assert signal.side == "HOLD"


def test_below_min_confidence_emits_hold(context) -> None:
    provider = MacdMomentumProvider(
        ProviderConfig(
            provider_id="macd_momentum",
            params={"min_confidence": 0.99},
        )
    )
    signal = provider.analyze(
        make_feature_set(
            indicators=_macd_features(
                macd_histogram=0.00001,
                macd_histogram_slope=0.00001,
            )
        ),
        context,
    )
    assert signal.side == "HOLD"
