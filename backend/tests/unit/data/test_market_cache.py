from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from src.core.exceptions import DataProviderError
from src.data import market_cache


@pytest.mark.asyncio
async def test_market_cache_uses_existing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(market_cache, "CACHE_DIR", tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 2, tzinfo=UTC)
    path = market_cache.cache_path(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=start,
        end=end,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "timestamp": [start],
            "open": [1.0],
            "high": [2.0],
            "low": [0.5],
            "close": [1.5],
            "volume": [10.0],
        }
    ).to_csv(path, index=False)

    called = {"download": False}

    def _fail_download(**kwargs: object) -> Path:
        called["download"] = True
        raise AssertionError("download should not run on cache hit")

    monkeypatch.setattr(market_cache, "_download_to_csv", _fail_download)

    result = await market_cache.get_or_download_csv(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=start,
        end=end,
    )
    assert result == path
    assert called["download"] is False


@pytest.mark.asyncio
async def test_market_cache_downloads_on_miss(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(market_cache, "CACHE_DIR", tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 2, tzinfo=UTC)
    expected = market_cache.cache_path(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=start,
        end=end,
    )

    def _download(**kwargs: object) -> Path:
        expected.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "timestamp": [start],
                "open": [1.0],
                "high": [2.0],
                "low": [0.5],
                "close": [1.5],
                "volume": [10.0],
            }
        ).to_csv(expected, index=False)
        return expected

    monkeypatch.setattr(market_cache, "_download_to_csv", _download)

    result = await market_cache.get_or_download_csv(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=start,
        end=end,
    )
    assert result == expected
    assert expected.exists()


def test_format_validation_error_messages() -> None:
    from src.api.services.validation_runner import format_validation_error

    assert (
        "date range"
        in format_validation_error(DataProviderError("No OHLCV bars in range for BTC/USDT")).lower()
    )
    assert (
        "internet"
        in format_validation_error(
            DataProviderError("Failed to download market data from binance: timeout")
        ).lower()
    )
    assert "sample csv" in format_validation_error(ValueError("No bars in range")).lower()
