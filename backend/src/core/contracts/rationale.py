from typing import Any, Literal

from pydantic import BaseModel, Field


class RationaleFactor(BaseModel, frozen=True):
    name: str
    weight: float = Field(ge=0.0, le=1.0)
    direction: Literal["bullish", "bearish", "neutral"]
    evidence: str


class ProviderRationale(BaseModel, frozen=True):
    summary: str
    factors: tuple[RationaleFactor, ...] = ()
    feature_refs: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskCheckResult(BaseModel, frozen=True):
    check_name: str
    passed: bool
    current_value: float
    threshold: float
    message: str


class RiskVerdict(BaseModel, frozen=True):
    passed: bool
    checks: tuple[RiskCheckResult, ...]
    state_snapshot_id: str
    risk_state_version: int
