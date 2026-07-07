from __future__ import annotations

import time
from datetime import datetime

import ccxt
import pandas as pd

from src.core.exceptions import DataProviderError


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
        df = self.get_latest(symbol, timeframe, limit=1000)
        if "timestamp" not in df.columns:
            return df
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if start_ts.tzinfo is None:
            start_ts = start_ts.tz_localize("UTC")
        else:
            start_ts = start_ts.tz_convert("UTC")
        if end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize("UTC")
        else:
            end_ts = end_ts.tz_convert("UTC")
        mask = (df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)
        return df.loc[mask].reset_index(drop=True)

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
