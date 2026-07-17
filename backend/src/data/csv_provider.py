from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.core.exceptions import DataProviderError


class CsvDataProvider:
    def __init__(self, path: Path, *, symbol: str = "BTC/USDT", timeframe: str = "1h") -> None:
        self._path = path
        self._symbol = symbol
        self._timeframe = timeframe
        self._df = self._load(path)

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def timeframe(self) -> str:
        return self._timeframe

    def timestamps(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[datetime]:
        self._validate_symbol_timeframe(symbol, timeframe)
        left, right = self._range_slice(start, end)
        return [ts.to_pydatetime() for ts in self._df["timestamp"].iloc[left:right]]

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        self._validate_symbol_timeframe(symbol, timeframe)
        left, right = self._range_slice(start, end)
        return self._df.iloc[left:right].reset_index(drop=True)

    def get_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        *,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        self._validate_symbol_timeframe(symbol, timeframe)
        if self._df.empty:
            raise DataProviderError("CSV OHLCV data is empty")
        if end is not None:
            end_ts = self._to_utc_ts(end)
            idx = int(self._df["timestamp"].searchsorted(end_ts, side="right"))
            if idx == 0:
                raise DataProviderError("No OHLCV rows on or before end time")
            start_idx = max(0, idx - limit)
            return self._df.iloc[start_idx:idx].reset_index(drop=True)
        if limit >= len(self._df):
            return self._df.reset_index(drop=True)
        return self._df.iloc[-limit:].reset_index(drop=True)

    def _range_slice(self, start: datetime, end: datetime) -> tuple[int, int]:
        start_ts = self._to_utc_ts(start)
        end_ts = self._to_utc_ts(end)
        left = int(self._df["timestamp"].searchsorted(start_ts, side="left"))
        right = int(self._df["timestamp"].searchsorted(end_ts, side="right"))
        return left, right

    def _validate_symbol_timeframe(self, symbol: str, timeframe: str) -> None:
        if symbol != self._symbol:
            raise DataProviderError(f"CSV provider only supports symbol {self._symbol}")
        if timeframe != self._timeframe:
            raise DataProviderError(f"CSV provider only supports timeframe {self._timeframe}")

    @staticmethod
    def _to_utc_ts(value: datetime) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")

    @staticmethod
    def _load(path: Path) -> pd.DataFrame:
        if not path.exists():
            raise DataProviderError(f"CSV file not found: {path}")
        df = pd.read_csv(path, parse_dates=["timestamp"])
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise DataProviderError(f"CSV missing columns: {sorted(missing)}")
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df.sort_values("timestamp").reset_index(drop=True)
