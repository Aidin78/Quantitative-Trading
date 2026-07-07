from __future__ import annotations

from dataclasses import dataclass

from src.core.contracts.context import MarketContext
from src.core.contracts.decision import Decision
from src.core.contracts.event import EventEnvelope
from src.core.contracts.features import FeatureSet
from src.core.contracts.signal import StrategySignal
from src.core.contracts.state import StateSnapshot


@dataclass(frozen=True)
class CycleResult:
    correlation_id: str
    feature_set: FeatureSet
    context: MarketContext
    snapshot: StateSnapshot
    signals: tuple[StrategySignal, ...]
    decision: Decision
    events: tuple[EventEnvelope, ...]
    execution_events: tuple[EventEnvelope, ...] = ()
