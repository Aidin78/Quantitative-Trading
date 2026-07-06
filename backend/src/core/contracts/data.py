from datetime import datetime
from typing import Any, Protocol

import pandas as pd


class MarketDataProvider(Protocol):
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame: ...

    def get_latest(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame: ...
