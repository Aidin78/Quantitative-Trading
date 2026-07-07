from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from src.core.exceptions import DataProviderError
from src.data.live_provider import LiveProvider


class _MockExchange:
    rateLimit = 1000

    def load_markets(self) -> dict:
        return {"BTC/USDT": {}}

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 200, since: int | None = None
    ) -> list:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        rows = []
        for i in range(limit):
            ts = int((base.timestamp() + i * 3600) * 1000)
            price = 100.0 + i
            rows.append([ts, price, price + 1, price - 1, price + 0.5, 10.0])
        if since is not None:
            rows = [row for row in rows if row[0] >= since]
        return rows


class _PaginatedMockExchange:
    rateLimit = 1000

    def parse_timeframe(self, timeframe: str) -> int:
        return 3600

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None = None,
        limit: int = 1000,
    ) -> list:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        all_rows = []
        for i in range(5):
            ts = int((base.timestamp() + i * 3600) * 1000)
            price = 100.0 + i
            all_rows.append([ts, price, price + 1, price - 1, price + 0.5, 10.0])
        filtered = [row for row in all_rows if since is None or row[0] >= since]
        return filtered[:limit]


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


def test_live_provider_fetch_ohlcv_range_paginates() -> None:
    provider = LiveProvider(exchange_id="binance")
    provider._exchange = _PaginatedMockExchange()  # noqa: SLF001
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 1, 4, 0, tzinfo=UTC)
    df = provider.fetch_ohlcv_range("BTC/USDT", "1h", start, end, limit=2)
    assert len(df) == 5
    assert df["timestamp"].min() >= pd.Timestamp(start)
    assert df["timestamp"].max() <= pd.Timestamp(end)


def test_live_provider_fetch_ohlcv_range_empty_raises() -> None:
    provider = LiveProvider(exchange_id="binance")
    provider._exchange = _PaginatedMockExchange()  # noqa: SLF001
    start = datetime(2027, 1, 1, tzinfo=UTC)
    end = datetime(2027, 1, 2, tzinfo=UTC)
    with pytest.raises(DataProviderError, match="No OHLCV data returned"):
        provider.fetch_ohlcv_range("BTC/USDT", "1h", start, end)
