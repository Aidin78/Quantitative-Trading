from __future__ import annotations

from pathlib import Path

import pytest

from src.core.exceptions import DataProviderError
from src.data.csv_provider import CsvDataProvider


@pytest.fixture
def csv_path() -> Path:
    path = Path(__file__).resolve().parents[2] / "fixtures" / "ohlcv_btc_1h.csv"
    if not path.exists():
        pytest.skip("ohlcv fixture missing")
    return path


def test_get_latest_returns_tail(csv_path: Path) -> None:
    provider = CsvDataProvider(csv_path)
    df = provider.get_latest("BTC/USDT", "1h", limit=50)
    assert len(df) == 50
    assert "close" in df.columns


def test_wrong_symbol_raises(csv_path: Path) -> None:
    provider = CsvDataProvider(csv_path)
    with pytest.raises(DataProviderError):
        provider.get_latest("ETH/USDT", "1h")


def test_get_latest_respects_end_time(csv_path: Path) -> None:
    from datetime import UTC, datetime

    provider = CsvDataProvider(csv_path)
    end = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    df = provider.get_latest("BTC/USDT", "1h", limit=200, end=end)
    assert df["timestamp"].max() <= end


def test_get_latest_does_not_mutate_source(csv_path: Path) -> None:
    provider = CsvDataProvider(csv_path)
    before = len(provider._df)
    _ = provider.get_latest("BTC/USDT", "1h", limit=10)
    assert len(provider._df) == before


def test_timestamps_uses_normalized_index(csv_path: Path) -> None:
    from datetime import UTC, datetime

    provider = CsvDataProvider(csv_path)
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
    stamps = provider.timestamps("BTC/USDT", "1h", start, end)
    assert stamps
    assert all(start <= ts <= end for ts in stamps)
    assert stamps == sorted(stamps)
