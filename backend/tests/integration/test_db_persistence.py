from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.contracts.event import EventEnvelope, EventFamily
from src.db.base import Base
from src.db.models import (
    DecisionRecordRow,
    EventLogRow,
    FeatureSetRow,
    FillRow,
    OrderRow,
    StateSnapshotRow,
)
from src.db.repositories.backtest import persist_event, persist_validation_result
from src.db.repositories.decision import persist_decision_from_event
from src.db.repositories.event_log import fetch_events_by_correlation
from src.events.envelopes import DecisionEventType, build_envelope
from src.replay.engine import ReplayEngine
from src.validation.harness import ValidationConfig, ValidationResult


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _sample_event(correlation_id: str = "cycle_db_1") -> EventEnvelope:
    now = datetime.now(UTC)
    return build_envelope(
        event_family=EventFamily.MARKET,
        event_type="CandleReceived",
        event_time=now,
        processing_time=now,
        correlation_id=correlation_id,
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={"close": 67000.0},
    )


@pytest.mark.asyncio
async def test_persist_event_roundtrip(db_session: AsyncSession) -> None:
    event = _sample_event()
    await persist_event(db_session, event)
    await db_session.commit()

    rows = (await db_session.execute(select(EventLogRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event_id == event.event_id


@pytest.mark.asyncio
async def test_replay_engine_from_db(db_session: AsyncSession) -> None:
    correlation_id = "replay_db_test"
    event = _sample_event(correlation_id)
    await persist_event(db_session, event)
    await db_session.commit()

    engine = await ReplayEngine.from_db(db_session, correlation_id)
    result = engine.replay_cycle(correlation_id)
    assert len(result.events) == 1
    assert result.events[0].correlation_id == correlation_id

    fetched = await fetch_events_by_correlation(db_session, correlation_id)
    assert len(fetched) == 1


@pytest.mark.asyncio
async def test_persist_order_and_fill_from_execution_events(db_session: AsyncSession) -> None:
    from src.events.envelopes import ExecutionEventType, build_envelope

    now = datetime.now(UTC)
    order_event = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.ORDER_SUBMITTED,
        event_time=now,
        processing_time=now,
        correlation_id="exec_db_1",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "order": {
                "order_id": "ord_test_1",
                "intent_id": "intent_test_1",
                "status": "submitted",
                "submitted_at": now.isoformat(),
                "venue": "simulator",
            },
            "venue": "simulator",
            "decision_id": "dec_test_1",
        },
    )
    fill_event = build_envelope(
        event_family=EventFamily.EXECUTION,
        event_type=ExecutionEventType.FILL_RECEIVED,
        event_time=now,
        processing_time=now,
        correlation_id="exec_db_1",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "fill": {
                "fill_id": "fill_test_1",
                "order_id": "ord_test_1",
                "price": 67000.0,
                "quantity": 0.01,
                "fee": 0.5,
                "slippage_bps": 5.0,
                "fill_time": now.isoformat(),
                "is_partial": False,
            },
            "fill_model_id": "close_price_v1",
        },
    )

    from src.db.repositories.order import persist_execution_event

    await persist_execution_event(db_session, order_event)
    await persist_execution_event(db_session, fill_event)
    await db_session.commit()

    orders = (await db_session.execute(select(OrderRow))).scalars().all()
    fills = (await db_session.execute(select(FillRow))).scalars().all()
    assert len(orders) == 1
    assert len(fills) == 1
    assert fills[0].order_id == "ord_test_1"


@pytest.mark.asyncio
async def test_persist_validation_result_stores_snapshots_and_features(
    db_session: AsyncSession,
) -> None:
    from src.core.contracts.decision import (
        AggregationResult,
        Decision,
        DecisionLog,
        DecisionResult,
        StageResult,
    )
    from src.core.contracts.features import FeatureSet
    from src.core.contracts.rationale import RiskVerdict
    from src.runtime.models import CycleResult
    from tests.mocks.fixtures import make_context, make_snapshot, utc_now

    now = utc_now()
    snapshot = make_snapshot()
    fs = FeatureSet(
        feature_set_id="fs_db_1",
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
        decision_id="dec_db",
        result=DecisionResult(value="approved"),
        decision_log=log,
        correlation_id="c_db",
        event_time=now,
        decision_time=now,
    )
    cycle = CycleResult(
        correlation_id="c_db",
        feature_set=fs,
        context=make_context(),
        snapshot=snapshot,
        signals=(),
        decision=decision,
        events=(),
    )
    result = ValidationResult(
        run_id=f"run_{uuid.uuid4().hex[:8]}",
        config=ValidationConfig(
            symbol="BTC/USDT",
            timeframe="1h",
            start=now,
            end=now,
        ),
        cycles=[cycle],
        events=[],
        engine_metrics={},
        outcome_metrics={},
    )
    await persist_validation_result(db_session, result)

    fs_rows = (await db_session.execute(select(FeatureSetRow))).scalars().all()
    snap_rows = (await db_session.execute(select(StateSnapshotRow))).scalars().all()
    assert len(fs_rows) == 1
    assert fs_rows[0].feature_set_id == "fs_db_1"
    assert len(snap_rows) == 1
    assert snap_rows[0].snapshot_id == snapshot.snapshot_id


@pytest.mark.asyncio
async def test_persist_decision_from_event_is_idempotent(db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    event = build_envelope(
        event_family=EventFamily.DECISION,
        event_type=DecisionEventType.DECISION_MADE,
        event_time=now,
        processing_time=now,
        correlation_id="dup_decision",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "decision_id": "dec_dup_test",
            "result": "rejected",
            "state_snapshot_id": "snap_1",
            "decision_log": {
                "market_filter": {"passed": False},
                "provider_signals": [],
                "aggregation": {"method": "majority", "side": "HOLD", "confidence": 0.5},
                "risk_check": {"passed": True, "checks": [], "state_snapshot_id": "snap_1"},
                "state_snapshot_id": "snap_1",
                "portfolio_version": 1,
                "risk_state_version": 1,
            },
        },
    )
    await persist_decision_from_event(db_session, event)
    await persist_decision_from_event(db_session, event)
    await db_session.commit()

    rows = (await db_session.execute(select(DecisionRecordRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].decision_id == "dec_dup_test"


@pytest.mark.asyncio
async def test_persist_validation_result_skips_existing_decisions(
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    decision_event = build_envelope(
        event_family=EventFamily.DECISION,
        event_type=DecisionEventType.DECISION_MADE,
        event_time=now,
        processing_time=now,
        correlation_id="val_cycle",
        symbol="BTC/USDT",
        timeframe="1h",
        mode="validation",
        payload={
            "decision_id": "dec_val_dup",
            "result": "rejected",
            "state_snapshot_id": "snap_val",
            "decision_log": {
                "market_filter": {"passed": False},
                "provider_signals": [],
                "aggregation": {"method": "majority", "side": "HOLD", "confidence": 0.5},
                "risk_check": {"passed": True, "checks": [], "state_snapshot_id": "snap_val"},
                "state_snapshot_id": "snap_val",
                "portfolio_version": 1,
                "risk_state_version": 1,
            },
        },
    )
    await persist_decision_from_event(db_session, decision_event)
    await db_session.commit()

    result = ValidationResult(
        run_id=f"run_{uuid.uuid4().hex[:8]}",
        config=ValidationConfig(
            symbol="BTC/USDT",
            timeframe="1h",
            start=now,
            end=now,
        ),
        cycles=[],
        events=[decision_event],
        engine_metrics={},
        outcome_metrics={},
    )
    await persist_validation_result(db_session, result)

    rows = (await db_session.execute(select(DecisionRecordRow))).scalars().all()
    assert len(rows) == 1
