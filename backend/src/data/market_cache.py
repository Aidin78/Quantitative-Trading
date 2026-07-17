from __future__ import annotations

import asyncio
import calendar
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from src.core.exceptions import DataProviderError
from src.core.settings import get_settings, resolve_config_dir
from src.data.live_provider import LiveProvider


def resolve_cache_dir() -> Path:
    """Resolve OHLCV cache directory (shared by Poetry and Docker).

    Priority:
    1. ``DATA_DIR`` env → ``{DATA_DIR}/cache``
    2. Sibling of config dir → ``{resolve_config_dir().parent}/data/cache``
    """
    backend_root = Path(__file__).resolve().parents[2]

    def _normalize(path: Path) -> Path:
        if path.is_absolute():
            return path.resolve()
        return (backend_root / path).resolve()

    if data_dir := os.environ.get("DATA_DIR"):
        return _normalize(Path(data_dir)) / "cache"
    return resolve_config_dir().parent / "data" / "cache"


# Mutable module attribute so tests can monkeypatch; production uses resolve_cache_dir().
CACHE_DIR = resolve_cache_dir()


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
    start: datetime | None = None,
    end: datetime | None = None,
) -> Path:
    """Continuous cache path: one CSV per exchange/symbol/timeframe.

    ``start`` / ``end`` are accepted for call-site compatibility but ignored —
    coverage is enforced by content, not filename.
    """
    del start, end
    safe_symbol = symbol.replace("/", "-")
    filename = f"{exchange_id}_{safe_symbol}_{timeframe}.csv"
    return CACHE_DIR / filename


def _parse_timestamp(value: str | datetime | pd.Timestamp) -> datetime:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.to_pydatetime()


def read_coverage(path: Path) -> tuple[datetime, datetime] | None:
    """Return (first_ts, last_ts) for a cache CSV, or None if empty/unreadable."""
    if not path.exists() or path.stat().st_size <= 0:
        return None
    summary = csv_summary(path)
    if not summary["rows"] or not summary["first_timestamp"] or not summary["last_timestamp"]:
        return None
    try:
        first = _parse_timestamp(summary["first_timestamp"])
        last = _parse_timestamp(summary["last_timestamp"])
    except (TypeError, ValueError):
        return None
    return first, last


def _fetch_ohlcv_df(
    *,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    settings = get_settings()
    provider = LiveProvider(
        exchange_id=exchange_id,
        api_key=settings.exchange_api_key,
        api_secret=settings.exchange_api_secret,
    )
    return provider.fetch_ohlcv_range(symbol, timeframe, start, end)


def _download_to_csv(
    *,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    path: Path,
) -> Path:
    """Fetch a range and write it to ``path`` (full replace). Kept for tests/tools."""
    df = _fetch_ohlcv_df(
        exchange_id=exchange_id,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
    )
    _write_ohlcv_atomic(path, df)
    return path


def _read_ohlcv_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def _merge_ohlcv(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        combined = new.copy()
    elif new.empty:
        combined = existing.copy()
    else:
        combined = pd.concat([existing, new], ignore_index=True)
    if combined.empty:
        return combined
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True)
    return (
        combined.drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


def _write_ohlcv_atomic(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def _try_fetch_gap(
    *,
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame | None:
    """Fetch a gap range; return None when the exchange has no bars in that window."""
    if start > end:
        return None
    try:
        return _fetch_ohlcv_df(
            exchange_id=exchange_id,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
    except DataProviderError as exc:
        if "No OHLCV bars" in str(exc):
            return None
        raise


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
    """Ensure continuous cache covers ``[start, end]``, extending via gap fetches.

    Returns ``(path, refreshed)`` where ``refreshed`` is True when the file was
    written or updated. ``force=True`` re-fetches the requested range and merges
    it into the continuous file (new bars win on duplicate timestamps).
    """
    path = cache_path(
        exchange_id=exchange_id,
        symbol=symbol,
        timeframe=timeframe,
    )
    start_utc = start.astimezone(UTC) if start.tzinfo else start.replace(tzinfo=UTC)
    end_utc = end.astimezone(UTC) if end.tzinfo else end.replace(tzinfo=UTC)

    try:
        coverage = read_coverage(path)

        if not force and coverage is not None:
            first, last = coverage
            if first <= start_utc and last >= end_utc:
                return path, False

        if force or coverage is None:
            new_df = await asyncio.to_thread(
                _fetch_ohlcv_df,
                exchange_id=exchange_id,
                symbol=symbol,
                timeframe=timeframe,
                start=start_utc,
                end=end_utc,
            )
            if coverage is not None and force:
                existing = await asyncio.to_thread(_read_ohlcv_csv, path)
                merged = _merge_ohlcv(existing, new_df)
                await asyncio.to_thread(_write_ohlcv_atomic, path, merged)
            else:
                await asyncio.to_thread(_write_ohlcv_atomic, path, new_df)
            return path, True

        first, last = coverage
        existing = await asyncio.to_thread(_read_ohlcv_csv, path)
        frames: list[pd.DataFrame] = [existing]
        wrote = False

        if start_utc < first:
            gap = await asyncio.to_thread(
                _try_fetch_gap,
                exchange_id=exchange_id,
                symbol=symbol,
                timeframe=timeframe,
                start=start_utc,
                end=first,
            )
            if gap is not None and not gap.empty:
                frames.append(gap)
                wrote = True

        if end_utc > last:
            gap = await asyncio.to_thread(
                _try_fetch_gap,
                exchange_id=exchange_id,
                symbol=symbol,
                timeframe=timeframe,
                start=last,
                end=end_utc,
            )
            if gap is not None and not gap.empty:
                frames.append(gap)
                wrote = True

        if not wrote:
            return path, False

        merged = frames[0]
        for frame in frames[1:]:
            merged = _merge_ohlcv(merged, frame)
        await asyncio.to_thread(_write_ohlcv_atomic, path, merged)
        return path, True
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
    path, _ = await download_csv(
        exchange_id=exchange_id,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        force=False,
    )
    return path
