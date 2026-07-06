from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.features.config import (
    ContextConfig,
    SessionContextConfig,
    TrendContextConfig,
    VolatilityContextConfig,
)
from src.features.context_deriver import ContextDeriver


@pytest.fixture
def deriver() -> ContextDeriver:
    config = ContextConfig(
        trend=TrendContextConfig(fast="ema_12", slow="ema_26"),
        volatility=VolatilityContextConfig(atr="atr_14", low=0.3, high=1.0),
        session=SessionContextConfig(),
    )
    return ContextDeriver(config)


def test_derive_trend_up(deriver: ContextDeriver) -> None:
    ctx = deriver.derive(
        symbol="BTC/USDT",
        timeframe="1h",
        close=67000.0,
        indicators={"ema_12": 68000.0, "ema_26": 66000.0, "atr_14": 400.0},
        event_time=datetime(2026, 1, 5, 10, 0, 0, tzinfo=UTC),
    )
    assert ctx.trend == "UP"
    assert ctx.volatility == "NORMAL"
    assert ctx.session == "EUROPE"


def test_derive_volatility_low(deriver: ContextDeriver) -> None:
    ctx = deriver.derive(
        symbol="BTC/USDT",
        timeframe="1h",
        close=67000.0,
        indicators={"ema_12": 67000.0, "ema_26": 67000.0, "atr_14": 100.0},
        event_time=datetime(2026, 1, 5, 14, 0, 0, tzinfo=UTC),
    )
    assert ctx.volatility == "LOW"
    assert ctx.session == "OVERLAP"


def test_derive_session_us(deriver: ContextDeriver) -> None:
    ctx = deriver.derive(
        symbol="BTC/USDT",
        timeframe="1h",
        close=67000.0,
        indicators={"ema_12": 65000.0, "ema_26": 66000.0, "atr_14": 900.0},
        event_time=datetime(2026, 1, 5, 18, 0, 0, tzinfo=UTC),
    )
    assert ctx.trend == "DOWN"
    assert ctx.volatility == "HIGH"
    assert ctx.session == "US"
