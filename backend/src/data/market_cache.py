from __future__ import annotations

import asyncio
import calendar
from datetime import UTC, datetime
from pathlib import Path

from src.core.exceptions import DataProviderError
from src.core.settings import get_settings
from src.data.live_provider import LiveProvider

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"


def subtract_months(dt: datetime, months: int) -> datetime:
    year = dt.year
    month = dt.month - months
    while month < 1:
        month += 12
        year -= 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, max_day)
    return dt.replace(year=year, month=month, day=day)


def resolve_range(
    *,
    start_date: str | None,
    end_date: str | None,
    months: int | None = None,
) -> tuple[datetime, datetime]:
    end = datetime.fromisoformat(end_date).replace(tzinfo=UTC) if end_date else datetime.now(UTC)
    if start_date:
        start = datetime.fromisoformat(start_date).replace(tzinfo=UTC)
    elif months is not None:
        start = subtract_months(end, months)
    else:
        start = subtract_months(end, 3)
    return start, end


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


def csv_summary(path: Path) -> dict:
    size_bytes = path.stat().st_size
    rows = 0
    first_ts: str | None = None
    last_ts: str | None = None
    last_line: str | None = None
    try:
        with path.open(encoding="utf-8") as handle:
            header = handle.readline()
            if not header:
                return {
                    "rows": 0,
                    "first_timestamp": None,
                    "last_timestamp": None,
                    "size_bytes": size_bytes,
                }
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                if rows == 0:
                    first_ts = stripped.split(",", 1)[0]
                rows += 1
                last_line = stripped
    except OSError:
        return {
            "rows": 0,
            "first_timestamp": None,
            "last_timestamp": None,
            "size_bytes": size_bytes,
        }
    if last_line is not None:
        last_ts = last_line.split(",", 1)[0]
    return {
        "rows": rows,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "size_bytes": size_bytes,
    }


def list_cache_entries() -> list[dict]:
    if not CACHE_DIR.exists():
        return []
    entries: list[dict] = []
    for path in sorted(
        CACHE_DIR.glob("*.csv"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        summary = csv_summary(path)
        entries.append(
            {
                "filename": path.name,
                "path": str(path),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
                **summary,
            }
        )
    return entries


def resolve_cache_file(filename: str) -> Path:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise DataProviderError("Invalid cache filename")
    path = (CACHE_DIR / filename).resolve()
    cache_root = CACHE_DIR.resolve()
    if not str(path).startswith(str(cache_root)):
        raise DataProviderError("Invalid cache filename")
    if not path.exists():
        raise DataProviderError("Cache file not found")
    return path


async def download_csv(
    *,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    force: bool = False,
) -> tuple[Path, bool]:
    path = cache_path(
        exchange_id=exchange_id,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
    )
    if path.exists() and path.stat().st_size > 0 and not force:
        return path, False
    try:
        downloaded = await asyncio.to_thread(
            _download_to_csv,
            exchange_id=exchange_id,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            path=path,
        )
        return downloaded, True
    except DataProviderError:
        raise
    except Exception as exc:
        raise DataProviderError(
            f"Failed to download market data from {exchange_id}: {exc}"
        ) from exc


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
    path, _ = await download_csv(
        exchange_id=exchange_id,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        force=False,
    )
    return path
