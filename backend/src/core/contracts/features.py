from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from src.core.contracts.context import MarketContext


class FeatureSet(BaseModel, frozen=True):
    feature_set_id: str
    symbol: str
    timeframe: str
    event_time: datetime
    processing_time: datetime
    feature_version: str
    config_hash: str
    close: float
    indicators: dict[str, float] = Field(default_factory=dict)
    flags: dict[str, bool] = Field(default_factory=dict)
    levels: dict[str, float] = Field(default_factory=dict)


class FeatureSetRecord(FeatureSet, frozen=True):
    schema_version: str = "v1"
    market_context: MarketContext | None = None


class FeatureBuilder(Protocol):
    def build(
        self,
        df: Any,
        symbol: str,
        timeframe: str,
    ) -> tuple[FeatureSet, MarketContext]: ...
