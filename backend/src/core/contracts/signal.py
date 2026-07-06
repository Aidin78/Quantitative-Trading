from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.core.contracts.rationale import ProviderRationale


class StrategySignal(BaseModel, frozen=True):
    provider_id: str
    symbol: str
    side: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: ProviderRationale
    feature_set_id: str
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    timeframe: str
    event_time: datetime
    valid_until_event_time: datetime | None = None


class FinalSignal(BaseModel, frozen=True):
    id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float = Field(ge=0.0, le=1.0)
    risk_reward: float
    timeframe: str
    event_time: datetime
    decision_time: datetime
    contributing_providers: tuple[str, ...]
    state_snapshot_id: str
    revision_id: str | None = None
