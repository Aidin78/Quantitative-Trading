from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.core.contracts.rationale import RiskVerdict
from src.core.contracts.signal import FinalSignal, StrategySignal


class StageResult(BaseModel, frozen=True):
    passed: bool
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AggregationResult(BaseModel, frozen=True):
    method: str
    side: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    weights: dict[str, float] = Field(default_factory=dict)
    dissent: tuple[str, ...] = ()


class DecisionLog(BaseModel, frozen=True):
    market_filter: StageResult
    provider_signals: tuple[StrategySignal, ...]
    aggregation: AggregationResult
    risk_check: RiskVerdict
    state_snapshot_id: str
    portfolio_version: int
    risk_state_version: int


class DecisionResult(BaseModel, frozen=True):
    value: Literal["approved", "rejected"]
    rejection_reason: str | None = None
    rejection_stage: Literal["market_filter", "aggregator", "risk_manager"] | None = None


class Decision(BaseModel, frozen=True):
    decision_id: str
    result: DecisionResult
    final_signal: FinalSignal | None = None
    decision_log: DecisionLog
    correlation_id: str
    event_time: datetime
    decision_time: datetime
    revision_id: str | None = None
    experiment_id: str | None = None

    @property
    def is_approved(self) -> bool:
        return self.result.value == "approved"
