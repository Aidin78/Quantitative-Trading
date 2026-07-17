from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from src.core.exceptions import DataProviderError
from src.data import market_cache


def _ohlcv_frame(timestamps: list[datetime]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [1.0] * len(timestamps),
            "high": [2.0] * len(timestamps),
            "low": [0.5] * len(timestamps),
            "close": [1.5] * len(timestamps),
            "volume": [10.0] * len(timestamps),
        }
    )


def _write_cache(path: Path, timestamps: list[datetime]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ohlcv_frame(timestamps).to_csv(path, index=False)


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
    )
    _write_cache(path, [start, end])

    called = {"download": False}

    def _fail_fetch(**kwargs: object) -> pd.DataFrame:
        called["download"] = True
        raise AssertionError("download should not run on coverage hit")

    monkeypatch.setattr(market_cache, "_fetch_ohlcv_df", _fail_fetch)

    result = await market_cache.get_or_download_csv(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=start,
        end=end,
    )
    assert result == path
    assert called["download"] is False
    assert path.name == "binance_BTC-USDT_1h.csv"


@pytest.mark.asyncio
async def test_coverage_hit_for_subset_range(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """File spanning Jan–Jun satisfies a Feb–May request without download."""
    monkeypatch.setattr(market_cache, "CACHE_DIR", tmp_path)
    path = market_cache.cache_path(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
    )
    _write_cache(
        path,
        [
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 6, 1, tzinfo=UTC),
        ],
    )

    def _fail_fetch(**kwargs: object) -> pd.DataFrame:
        raise AssertionError("subset range must be a coverage hit")

    monkeypatch.setattr(market_cache, "_fetch_ohlcv_df", _fail_fetch)

    result = await market_cache.get_or_download_csv(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=datetime(2026, 2, 1, tzinfo=UTC),
        end=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert result == path


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
    )

    def _fetch(**kwargs: object) -> pd.DataFrame:
        return _ohlcv_frame([start])

    monkeypatch.setattr(market_cache, "_fetch_ohlcv_df", _fetch)

    result = await market_cache.get_or_download_csv(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=start,
        end=end,
    )
    assert result == expected
    assert expected.exists()
    assert expected.name == "binance_BTC-USDT_1h.csv"


@pytest.mark.asyncio
async def test_append_only_gap_fetch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(market_cache, "CACHE_DIR", tmp_path)
    path = market_cache.cache_path(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
    )
    first = datetime(2026, 1, 1, tzinfo=UTC)
    last = datetime(2026, 1, 10, tzinfo=UTC)
    new_end = datetime(2026, 1, 15, tzinfo=UTC)
    _write_cache(path, [first, last])

    calls: list[tuple[datetime, datetime]] = []

    def _fetch(*, start, end, **kwargs):  # noqa: ANN001
        calls.append((start, end))
        return _ohlcv_frame([last + timedelta(hours=1), new_end])

    monkeypatch.setattr(market_cache, "_fetch_ohlcv_df", _fetch)

    result, refreshed = await market_cache.download_csv(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=first,
        end=new_end,
        force=False,
    )
    assert result == path
    assert refreshed is True
    assert len(calls) == 1
    assert calls[0][0] == last
    assert calls[0][1] == new_end
    summary = market_cache.csv_summary(path)
    assert summary["rows"] == 4


@pytest.mark.asyncio
async def test_prepend_only_gap_fetch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(market_cache, "CACHE_DIR", tmp_path)
    path = market_cache.cache_path(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
    )
    first = datetime(2026, 1, 10, tzinfo=UTC)
    last = datetime(2026, 1, 20, tzinfo=UTC)
    new_start = datetime(2026, 1, 1, tzinfo=UTC)
    _write_cache(path, [first, last])

    calls: list[tuple[datetime, datetime]] = []

    def _fetch(*, start, end, **kwargs):  # noqa: ANN001
        calls.append((start, end))
        return _ohlcv_frame([new_start, first - timedelta(hours=1)])

    monkeypatch.setattr(market_cache, "_fetch_ohlcv_df", _fetch)

    result, refreshed = await market_cache.download_csv(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=new_start,
        end=last,
        force=False,
    )
    assert result == path
    assert refreshed is True
    assert len(calls) == 1
    assert calls[0][0] == new_start
    assert calls[0][1] == first
    coverage = market_cache.read_coverage(path)
    assert coverage is not None
    assert coverage[0] == new_start
    assert coverage[1] == last


@pytest.mark.asyncio
async def test_merge_dedupes_overlapping_timestamps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(market_cache, "CACHE_DIR", tmp_path)
    path = market_cache.cache_path(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
    )
    first = datetime(2026, 1, 1, tzinfo=UTC)
    last = datetime(2026, 1, 5, tzinfo=UTC)
    new_end = datetime(2026, 1, 8, tzinfo=UTC)
    _write_cache(path, [first, last])

    def _fetch(*, start, end, **kwargs):  # noqa: ANN001
        # Overlap on ``last`` plus one new bar — merge must keep a single last.
        return _ohlcv_frame([last, new_end])

    monkeypatch.setattr(market_cache, "_fetch_ohlcv_df", _fetch)

    await market_cache.download_csv(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=first,
        end=new_end,
        force=False,
    )
    df = pd.read_csv(path)
    assert len(df) == 3
    assert df["timestamp"].duplicated().sum() == 0


@pytest.mark.asyncio
async def test_download_csv_force_redownloads(
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
    )
    _write_cache(expected, [start])

    calls = {"count": 0}

    def _fetch(**kwargs: object) -> pd.DataFrame:
        calls["count"] += 1
        return _ohlcv_frame([start, end])

    monkeypatch.setattr(market_cache, "_fetch_ohlcv_df", _fetch)

    path, refreshed = await market_cache.download_csv(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=start,
        end=end,
        force=True,
    )
    assert path == expected
    assert refreshed is True
    assert calls["count"] == 1
    assert market_cache.csv_summary(path)["rows"] == 2


@pytest.mark.asyncio
async def test_empty_file_treated_as_miss(
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
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")

    def _fetch(**kwargs: object) -> pd.DataFrame:
        return _ohlcv_frame([start])

    monkeypatch.setattr(market_cache, "_fetch_ohlcv_df", _fetch)

    result = await market_cache.get_or_download_csv(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=start,
        end=end,
    )
    assert result == path
    assert market_cache.csv_summary(path)["rows"] == 1


def test_format_validation_error_messages() -> None:
    from src.validation.errors import format_validation_error

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


def test_resolve_cache_dir_uses_config_parent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setattr(market_cache, "resolve_config_dir", lambda: config_dir)

    assert market_cache.resolve_cache_dir() == tmp_path / "data" / "cache"


def test_resolve_cache_dir_prefers_data_dir_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "custom-data"
    data_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(data_dir))

    assert market_cache.resolve_cache_dir() == data_dir / "cache"


def test_cache_path_continuous_naming(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(market_cache, "CACHE_DIR", tmp_path)
    path = market_cache.cache_path(
        exchange_id="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 6, 1, tzinfo=UTC),
    )
    assert path.name == "binance_BTC-USDT_1h.csv"
