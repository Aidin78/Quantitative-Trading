from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MarketContext(BaseModel, frozen=True):
    symbol: str
    timeframe: str
    current_price: float
    trend: Literal["UP", "DOWN", "SIDEWAYS"]
    volatility: Literal["LOW", "NORMAL", "HIGH"]
    atr: float
    atr_pct: float
    session: Literal["ASIA", "EUROPE", "US", "OVERLAP"]
    event_time: datetime
