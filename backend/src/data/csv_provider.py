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

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        self._validate_symbol_timeframe(symbol, timeframe)
        df = self._df.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            mask = (df["timestamp"] >= pd.Timestamp(start, tz="UTC")) & (
                df["timestamp"] <= pd.Timestamp(end, tz="UTC")
            )
            return df.loc[mask].reset_index(drop=True)
        return df

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
        df = self._df.copy()
        if end is not None and "timestamp" in df.columns:
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

    def _validate_symbol_timeframe(self, symbol: str, timeframe: str) -> None:
        if symbol != self._symbol:
            raise DataProviderError(f"CSV provider only supports symbol {self._symbol}")
        if timeframe != self._timeframe:
            raise DataProviderError(f"CSV provider only supports timeframe {self._timeframe}")

    @staticmethod
    def _load(path: Path) -> pd.DataFrame:
        if not path.exists():
            raise DataProviderError(f"CSV file not found: {path}")
        df = pd.read_csv(path, parse_dates=["timestamp"])
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise DataProviderError(f"CSV missing columns: {sorted(missing)}")
        return df.sort_values("timestamp").reset_index(drop=True)
