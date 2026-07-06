"""Contract import and schema smoke tests."""

from datetime import datetime, timezone

from src.core.contracts import (
    ConfigRevision,
    Decision,
    EventEnvelope,
    EventFamily,
    FeatureSet,
    FinalSignal,
    PortfolioState,
    ProviderRationale,
    RiskLimits,
    RiskState,
    StateSnapshot,
    StrategySignal,
)
from src.core.contracts.decision import AggregationResult, DecisionLog, DecisionResult, StageResult
from src.core.contracts.rationale import RiskCheckResult, RiskVerdict


def test_contracts_import_without_implementation() -> None:
    now = datetime.now(timezone.utc)
    rationale = ProviderRationale(summary="test", factors=())
    signal = StrategySignal(
        provider_id="ema_crossover",
        symbol="BTC/USDT",
        side="BUY",
        confidence=0.7,
        rationale=rationale,
        feature_set_id="fs_001",
        timeframe="1h",
        event_time=now,
    )
    limits = RiskLimits(
        max_daily_drawdown_pct=5.0,
        max_open_positions=3,
        max_exposure_pct=50.0,
    )
    portfolio = PortfolioState(
        portfolio_id="p1",
        mode="validation",
        cash=10000.0,
        equity=10000.0,
        version=1,
        as_of_event_time=now,
        as_of_processing_time=now,
    )
    risk = RiskState(
        risk_state_id="r1",
        portfolio_id="p1",
        limits=limits,
        version=1,
        as_of_event_time=now,
    )
    snapshot = StateSnapshot(
        snapshot_id="snap_001",
        portfolio=portfolio,
        risk=risk,
        version=1,
        created_at=now,
    )
    verdict = RiskVerdict(
        passed=True,
        checks=(
            RiskCheckResult(
                check_name="daily_drawdown",
                passed=True,
                current_value=1.0,
                threshold=5.0,
                message="ok",
            ),
        ),
        state_snapshot_id="snap_001",
        risk_state_version=1,
    )
    log = DecisionLog(
        market_filter=StageResult(passed=True),
        provider_signals=(signal,),
        aggregation=AggregationResult(method="weighted", side="BUY", confidence=0.7),
        risk_check=verdict,
        state_snapshot_id="snap_001",
        portfolio_version=1,
        risk_state_version=1,
    )
    decision = Decision(
        decision_id="dec_001",
        result=DecisionResult(value="approved"),
        final_signal=FinalSignal(
            id="sig_001",
            symbol="BTC/USDT",
            side="BUY",
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            confidence=0.7,
            risk_reward=2.0,
            timeframe="1h",
            event_time=now,
            decision_time=now,
            contributing_providers=("ema_crossover",),
            state_snapshot_id="snap_001",
        ),
        decision_log=log,
        correlation_id="cycle_001",
        event_time=now,
        decision_time=now,
    )
    envelope = EventEnvelope(
        event_id="evt_001",
        event_family=EventFamily.DECISION,
        event_type="DecisionApproved",
        event_time=now,
        processing_time=now,
        correlation_id="cycle_001",
        cycle_id="cycle_001",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={"decision_id": decision.decision_id},
    )
    revision = ConfigRevision(
        revision_id="rev_001",
        created_at=now,
        engine_config_hash="abc",
        features_config_hash="def",
        providers_config_hash="ghi",
        risk_limits_hash="jkl",
        label="baseline",
    )
    assert decision.is_approved
    assert envelope.event_family == EventFamily.DECISION
    assert revision.revision_id == "rev_001"
    assert isinstance(FeatureSet, type)
