from __future__ import annotations

import time
from datetime import datetime

import ccxt
import pandas as pd

from src.core.exceptions import DataProviderError


def _to_utc_timestamp(value: datetime) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


class LiveProvider:
    """Fetches OHLCV from a live exchange via ccxt."""

    def __init__(
        self,
        *,
        exchange_id: str = "binance",
        api_key: str = "",
        api_secret: str = "",
    ) -> None:
        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise DataProviderError(f"Unsupported exchange: {exchange_id}")
        config: dict = {"enableRateLimit": True}
        if api_key:
            config["apiKey"] = api_key
            config["secret"] = api_secret
        self._exchange = exchange_class(config)
        self._exchange_id = exchange_id

    @property
    def exchange_id(self) -> str:
        return self._exchange_id

    def ping(self) -> bool:
        try:
            self._exchange.load_markets()
            return True
        except Exception:
            return False

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        return self.fetch_ohlcv_range(symbol, timeframe, start, end)

    def fetch_ohlcv_range(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        *,
        limit: int = 1000,
    ) -> pd.DataFrame:
        start_ts = _to_utc_timestamp(start)
        end_ts = _to_utc_timestamp(end)
        if start_ts > end_ts:
            raise DataProviderError("Start date must be on or before end date")

        timeframe_ms = int(self._exchange.parse_timeframe(timeframe) * 1000)
        since_ms = int(start_ts.timestamp() * 1000)
        end_ms = int(end_ts.timestamp() * 1000)
        all_rows: list[list] = []
        last_error: Exception | None = None

        while since_ms <= end_ms:
            batch: list | None = None
            for attempt in range(3):
                try:
                    batch = self._exchange.fetch_ohlcv(
                        symbol,
                        timeframe,
                        since=since_ms,
                        limit=limit,
                    )
                    break
                except ccxt.RateLimitExceeded as exc:
                    last_error = exc
                    time.sleep((self._exchange.rateLimit / 1000) * (attempt + 1))
                except Exception as exc:
                    last_error = exc
                    time.sleep(1)
            if batch is None:
                raise DataProviderError(
                    f"Failed to fetch historical OHLCV for {symbol}: {last_error}"
                ) from last_error
            if not batch:
                break
            all_rows.extend(batch)
            last_ts = batch[-1][0]
            if last_ts >= end_ms:
                break
            next_since = last_ts + timeframe_ms
            if next_since <= since_ms:
                break
            since_ms = next_since

        if not all_rows:
            raise DataProviderError(
                f"No OHLCV data returned for {symbol} {timeframe} "
                f"between {start_ts.isoformat()} and {end_ts.isoformat()}"
            )

        df = self._to_dataframe(all_rows)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
        mask = (df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)
        filtered = df.loc[mask].reset_index(drop=True)
        if filtered.empty:
            raise DataProviderError(
                f"No OHLCV bars in range for {symbol} {timeframe} "
                f"between {start_ts.isoformat()} and {end_ts.isoformat()}"
            )
        return filtered

    def get_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        *,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                ohlcv = self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = self._to_dataframe(ohlcv)
                if end is not None:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                    end_ts = pd.Timestamp(end)
                    if end_ts.tzinfo is None:
                        end_ts = end_ts.tz_localize("UTC")
                    else:
                        end_ts = end_ts.tz_convert("UTC")
                    df = df[df["timestamp"] <= end_ts]
                    if df.empty:
                        raise DataProviderError("No OHLCV rows on or before end time")
                return df.tail(limit).reset_index(drop=True)
            except ccxt.RateLimitExceeded as exc:
                last_error = exc
                time.sleep((self._exchange.rateLimit / 1000) * (attempt + 1))
            except DataProviderError:
                raise
            except Exception as exc:
                last_error = exc
                time.sleep(1)
        raise DataProviderError(f"Failed to fetch OHLCV for {symbol}: {last_error}") from last_error

    @staticmethod
    def _to_dataframe(ohlcv: list) -> pd.DataFrame:
        if not ohlcv:
            raise DataProviderError("Exchange returned empty OHLCV")
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df.sort_values("timestamp").reset_index(drop=True)
