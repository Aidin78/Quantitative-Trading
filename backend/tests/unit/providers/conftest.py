from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet


def utc_now() -> datetime:
    return datetime(2026, 7, 6, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def context() -> MarketContext:
    return MarketContext(
        symbol="BTC/USDT",
        timeframe="1h",
        current_price=67000.0,
        trend="UP",
        volatility="NORMAL",
        atr=335.0,
        atr_pct=0.5,
        session="EUROPE",
        event_time=utc_now(),
    )


def make_feature_set(
    *,
    close: float = 67000.0,
    flags: dict[str, bool] | None = None,
    indicators: dict[str, float] | None = None,
) -> FeatureSet:
    now = utc_now()
    return FeatureSet(
        feature_set_id="fs_test_001",
        symbol="BTC/USDT",
        timeframe="1h",
        event_time=now,
        processing_time=now,
        feature_version="v1",
        config_hash="abc123",
        close=close,
        indicators=indicators or {},
        flags=flags or {},
    )
