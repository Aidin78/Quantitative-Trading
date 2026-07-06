from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StateTransitionEvent(BaseModel, frozen=True):
    transition_id: str
    portfolio_id: str
    transition_type: Literal[
        "position_opened",
        "position_closed",
        "risk_updated",
        "portfolio_updated",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    event_time: datetime
    correlation_id: str
