from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from src.core.exceptions import DataProviderError
from src.core.settings import get_settings
from src.data.live_provider import LiveProvider

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"


def cache_path(
    *,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> Path:
    safe_symbol = symbol.replace("/", "-")
    start_key = start.astimezone(UTC).strftime("%Y%m%d")
    end_key = end.astimezone(UTC).strftime("%Y%m%d")
    filename = f"{exchange_id}_{safe_symbol}_{timeframe}_{start_key}_{end_key}.csv"
    return CACHE_DIR / filename


def _download_to_csv(
    *,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    path: Path,
) -> Path:
    settings = get_settings()
    provider = LiveProvider(
        exchange_id=exchange_id,
        api_key=settings.exchange_api_key,
        api_secret=settings.exchange_api_secret,
    )
    df = provider.fetch_ohlcv_range(symbol, timeframe, start, end)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


async def get_or_download_csv(
    *,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> Path:
    path = cache_path(
        exchange_id=exchange_id,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
    )
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        return await asyncio.to_thread(
            _download_to_csv,
            exchange_id=exchange_id,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            path=path,
        )
    except DataProviderError:
        raise
    except Exception as exc:
        raise DataProviderError(
            f"Failed to download market data from {exchange_id}: {exc}"
        ) from exc
