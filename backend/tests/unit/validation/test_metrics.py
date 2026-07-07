from __future__ import annotations

from src.core.contracts.event import EventFamily
from src.runtime.models import CycleResult
from src.validation.metrics import compute_engine_metrics, compute_outcome_metrics
from tests.mocks.fixtures import make_context, make_snapshot, utc_now


def _minimal_cycle(*, approved: bool = True) -> CycleResult:
    from src.core.contracts.decision import (
        AggregationResult,
        Decision,
        DecisionLog,
        DecisionResult,
        StageResult,
    )
    from src.core.contracts.features import FeatureSet
    from src.core.contracts.rationale import RiskVerdict

    now = utc_now()
    snapshot = make_snapshot()
    log = DecisionLog(
        market_filter=StageResult(passed=True),
        provider_signals=(),
        aggregation=AggregationResult(method="majority", side="BUY", confidence=0.8),
        risk_check=RiskVerdict(
            passed=True,
            checks=(),
            state_snapshot_id=snapshot.snapshot_id,
            risk_state_version=1,
        ),
        state_snapshot_id=snapshot.snapshot_id,
        portfolio_version=1,
        risk_state_version=1,
    )
    decision = Decision(
        decision_id="d1",
        result=DecisionResult(
            value="approved" if approved else "rejected", rejection_reason="low_confidence"
        ),
        decision_log=log,
        correlation_id="c1",
        event_time=now,
        decision_time=now,
    )
    fs = FeatureSet(
        feature_set_id="fs1",
        symbol="BTC/USDT",
        timeframe="1h",
        event_time=now,
        processing_time=now,
        feature_version="v1",
        config_hash="abc",
        close=67000.0,
        indicators={},
        flags={},
    )
    return CycleResult(
        correlation_id="c1",
        feature_set=fs,
        context=make_context(),
        snapshot=snapshot,
        signals=(),
        decision=decision,
        events=(),
    )


def test_approval_rate() -> None:
    cycles = [_minimal_cycle(approved=True), _minimal_cycle(approved=False)]
    metrics = compute_engine_metrics(cycles, [])
    assert metrics["approval_rate"] == 0.5
    assert metrics["approved"] == 1
    assert metrics["rejected"] == 1


def test_outcome_metrics_from_closed_positions() -> None:
    from src.events.envelopes import ExecutionEventType, build_envelope

    now = utc_now()
    events = [
        build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=now,
            processing_time=now,
            correlation_id="c1",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "pnl": 100.0,
                "position_id": "p1",
                "exit_reason": "take_profit",
                "fill_id": "f1",
            },
        ),
        build_envelope(
            event_family=EventFamily.EXECUTION,
            event_type=ExecutionEventType.POSITION_CLOSED,
            event_time=now,
            processing_time=now,
            correlation_id="c2",
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "pnl": -50.0,
                "position_id": "p2",
                "exit_reason": "stop_loss",
                "fill_id": "f2",
            },
        ),
    ]
    om = compute_outcome_metrics(events)
    assert om["total_trades"] == 2
    assert om["win_rate"] == 0.5
    assert om["total_pnl"] == 50.0
