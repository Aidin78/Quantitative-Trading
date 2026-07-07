from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.contracts.decision import (
    AggregationResult,
    Decision,
    DecisionLog,
    DecisionResult,
    StageResult,
)
from src.core.contracts.event import EventFamily
from src.core.contracts.rationale import ProviderRationale, RiskVerdict
from src.core.contracts.signal import StrategySignal
from src.db.base import Base
from src.db.models import StateSnapshotRow
from src.db.repositories.backtest import persist_event
from src.events.envelopes import (
    DecisionEventType,
    MarketEventType,
    SignalEventType,
    build_envelope,
)
from src.replay.diff import build_decision_diff
from src.replay.engine import ReplayEngine
from src.replay.reexecutor import re_execute_cycle
from tests.mocks.fixtures import make_context, make_snapshot, utc_now


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _provider_signal() -> StrategySignal:
    now = utc_now()
    return StrategySignal(
        provider_id="ema_crossover",
        symbol="BTC/USDT",
        side="BUY",
        confidence=0.8,
        rationale=ProviderRationale(summary="test"),
        feature_set_id="fs_replay",
        timeframe="1h",
        event_time=now,
    )


@pytest.mark.asyncio
async def test_re_execute_produces_decision_diff(db_session: AsyncSession) -> None:
    now = utc_now()
    correlation_id = "reexec_test"
    snapshot = make_snapshot()
    db_session.add(
        StateSnapshotRow(
            snapshot_id=snapshot.snapshot_id,
            correlation_id=correlation_id,
            portfolio=snapshot.portfolio.model_dump(mode="json"),
            risk=snapshot.risk.model_dump(mode="json"),
            version=snapshot.version,
            created_at=now,
        )
    )
    signal = _provider_signal()
    context = make_context()
    log = DecisionLog(
        market_filter=StageResult(passed=True),
        provider_signals=(signal,),
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
    events = [
        build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.FEATURE_SET_BUILT,
            event_time=now,
            processing_time=now,
            correlation_id=correlation_id,
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "feature_set_id": "fs_replay",
                "feature_version": "v1",
                "config_hash": "abc",
                "indicators": {},
                "flags": {},
            },
        ),
        build_envelope(
            event_family=EventFamily.MARKET,
            event_type=MarketEventType.MARKET_CONTEXT_DERIVED,
            event_time=now,
            processing_time=now,
            correlation_id=correlation_id,
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload=context.model_dump(mode="json"),
        ),
        build_envelope(
            event_family=EventFamily.SIGNAL,
            event_type=SignalEventType.PROVIDER_OPINION,
            event_time=now,
            processing_time=now,
            correlation_id=correlation_id,
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "provider_id": signal.provider_id,
                "side": signal.side,
                "confidence": signal.confidence,
                "rationale": signal.rationale.model_dump(mode="json"),
            },
        ),
        build_envelope(
            event_family=EventFamily.DECISION,
            event_type=DecisionEventType.DECISION_MADE,
            event_time=now,
            processing_time=now,
            correlation_id=correlation_id,
            symbol="BTC/USDT",
            timeframe="1h",
            mode="validation",
            payload={
                "decision_id": "dec_reexec",
                "result": "approved",
                "state_snapshot_id": snapshot.snapshot_id,
                "decision_log": log.model_dump(mode="json"),
            },
        ),
    ]
    for event in events:
        await persist_event(db_session, event)
    await db_session.commit()

    _, diff, _drift = await re_execute_cycle(db_session, events)
    assert diff.correlation_id == correlation_id
    assert diff.original_result == "approved"
    assert diff.reexecuted_result in ("approved", "rejected")

    engine = ReplayEngine(events)
    result = await engine.replay_cycle_async(db_session, correlation_id, mode="re_execute")
    assert result.mode == "re_execute"
    assert result.decision_diff is not None


def test_build_decision_diff_detects_change() -> None:
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
    original = Decision(
        decision_id="d1",
        result=DecisionResult(value="approved"),
        decision_log=log,
        correlation_id="c1",
        event_time=now,
        decision_time=now,
    )
    reexecuted = Decision(
        decision_id="d2",
        result=DecisionResult(value="rejected", rejection_reason="risk"),
        decision_log=log,
        correlation_id="c1",
        event_time=now,
        decision_time=now,
    )
    diff = build_decision_diff("c1", original, reexecuted)
    assert diff.changed is True
