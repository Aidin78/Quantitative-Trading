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
    """Outcome of one ``PlatformRuntime.run_cycle``.

    ``snapshot`` is the **decision-time** state: after pre-decision
    ``evaluate_bar`` (pending fills, SL/TP/timeout) and before same-bar
    signal exit / ``execute``. It is not a post-trade portfolio snapshot.
    """

    correlation_id: str
    feature_set: FeatureSet
    context: MarketContext
    snapshot: StateSnapshot
    signals: tuple[StrategySignal, ...]
    decision: Decision
    events: tuple[EventEnvelope, ...]
    execution_events: tuple[EventEnvelope, ...] = ()
