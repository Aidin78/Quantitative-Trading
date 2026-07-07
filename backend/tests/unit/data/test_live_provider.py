from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from src.data.live_provider import LiveProvider


class _MockExchange:
    rateLimit = 1000

    def load_markets(self) -> dict:
        return {"BTC/USDT": {}}

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        rows = []
        for i in range(limit):
            ts = int((base.timestamp() + i * 3600) * 1000)
            price = 100.0 + i
            rows.append([ts, price, price + 1, price - 1, price + 0.5, 10.0])
        return rows


def test_live_provider_get_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = LiveProvider(exchange_id="binance")
    provider._exchange = _MockExchange()  # noqa: SLF001
    df = provider.get_latest("BTC/USDT", "1h", limit=5)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 5


def test_live_provider_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = LiveProvider(exchange_id="binance")
    provider._exchange = _MockExchange()  # noqa: SLF001
    assert provider.ping() is True
