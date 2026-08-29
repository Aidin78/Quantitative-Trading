"""Perpetual funding-rate history: download from the exchange (ccxt) and cache
to CSV under the shared market cache dir. ``market_cache`` itself only handles
OHLCV, so funding gets its own small loader here.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.data.market_cache import resolve_cache_dir


def _cache_path(exchange_id: str, symbol: str) -> Path:
    safe = symbol.replace("/", "-")
    return resolve_cache_dir() / f"{exchange_id}_funding_{safe}_8h.csv"


def _perp_symbol(spot_symbol: str) -> str:
    base, quote = spot_symbol.split("/")
    return f"{base}/{quote}:{quote}"


def _read_cache(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, format="ISO8601")
    return frame


def _covers(frame: pd.DataFrame, start: datetime, end: datetime) -> bool:
    return (
        not frame.empty
        and frame["timestamp"].iloc[0] <= pd.Timestamp(start)
        and frame["timestamp"].iloc[-1] >= pd.Timestamp(end) - pd.Timedelta(days=2)
    )


def _download(exchange_id: str, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    import ccxt

    exchange = getattr(ccxt, exchange_id)({"options": {"defaultType": "future"}, "timeout": 20000})
    perp = _perp_symbol(symbol)
    since = exchange.parse8601(start.strftime("%Y-%m-%dT%H:%M:%SZ"))
    end_ms = exchange.parse8601(end.strftime("%Y-%m-%dT%H:%M:%SZ"))
    rows: list[dict] = []
    while since < end_ms:
        batch = exchange.fetch_funding_rate_history(perp, since=since, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        since = batch[-1]["timestamp"] + 1
        if len(batch) < 1000:
            break
    return (
        pd.DataFrame(
            {
                "timestamp": pd.to_datetime([r["timestamp"] for r in rows], unit="ms", utc=True),
                "funding_rate": [float(r["fundingRate"]) for r in rows],
            }
        )
        .drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


def load_funding_history(
    symbol: str,
    start: datetime,
    end: datetime,
    *,
    exchange_id: str = "binance",
) -> pd.DataFrame:
    """Full funding-rate history (8h cadence) for the perp of ``symbol``.

    Returns a frame with ``timestamp`` (UTC) and ``funding_rate`` (per 8h, as a
    fraction — e.g. 0.0001 = 1 bp). Cached to CSV; a cache that already spans
    ``[start, end]`` is reused without hitting the network.
    """
    path = _cache_path(exchange_id, symbol)
    cached = _read_cache(path)
    if cached is not None and _covers(cached, start, end):
        frame = cached
    else:
        frame = _download(exchange_id, symbol, start, end)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    mask = (frame["timestamp"] >= pd.Timestamp(start)) & (frame["timestamp"] <= pd.Timestamp(end))
    return frame.loc[mask].reset_index(drop=True)
