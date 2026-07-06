from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSetRecord
from src.features.store import InMemoryFeatureStore


def _record(feature_set_id: str, event_time: datetime) -> FeatureSetRecord:
    ctx = MarketContext(
        symbol="BTC/USDT",
        timeframe="1h",
        current_price=67000.0,
        trend="UP",
        volatility="NORMAL",
        atr=400.0,
        atr_pct=0.6,
        session="EUROPE",
        event_time=event_time,
    )
    return FeatureSetRecord(
        feature_set_id=feature_set_id,
        symbol="BTC/USDT",
        timeframe="1h",
        event_time=event_time,
        processing_time=event_time,
        feature_version="v1",
        config_hash="abc",
        close=67000.0,
        indicators={"rsi_14": 55.0},
        flags={"ema_cross_bullish": True},
        market_context=ctx,
    )


def test_store_put_get() -> None:
    store = InMemoryFeatureStore()
    event_time = datetime(2026, 1, 5, 10, 0, 0, tzinfo=UTC)
    record = _record("fs_001", event_time)
    store.put(record)
    assert store.get("fs_001") == record
    assert store.size == 1


def test_store_get_at() -> None:
    store = InMemoryFeatureStore()
    event_time = datetime(2026, 1, 5, 10, 0, 0, tzinfo=UTC)
    store.put(_record("fs_001", event_time))
    found = store.get_at("BTC/USDT", "1h", event_time, "v1")
    assert found is not None
    assert found.feature_set_id == "fs_001"


def test_store_get_missing_raises() -> None:
    store = InMemoryFeatureStore()
    with pytest.raises(KeyError):
        store.get("missing")
