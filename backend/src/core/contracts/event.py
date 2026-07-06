from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class EventFamily(StrEnum):
    MARKET = "market"
    SIGNAL = "signal"
    DECISION = "decision"
    EXECUTION = "execution"
    OPERATIONAL = "operational"


class EventEnvelope(BaseModel, frozen=True):
    event_id: str
    event_family: EventFamily
    event_type: str
    schema_version: str = "v1"
    event_time: datetime
    processing_time: datetime
    correlation_id: str
    causation_id: str | None = None
    cycle_id: str
    symbol: str
    timeframe: str
    mode: Literal["validation", "live", "paper", "replay"]
    experiment_id: str | None = None
    revision_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EventBus(Protocol):
    async def publish(self, event: EventEnvelope) -> None: ...

    async def publish_many(self, events: list[EventEnvelope]) -> None: ...


class EventHandler(Protocol):
    event_types: set[str]

    async def handle(self, event: EventEnvelope) -> None: ...
