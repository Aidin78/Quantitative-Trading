from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.event import EventEnvelope
from src.db.models import (
    BacktestRunRow,
    EventLogRow,
    FeatureSetRow,
    SimulatedTradeRow,
    StateSnapshotRow,
)
from src.events.envelopes import ExecutionEventType
from src.validation.harness import ValidationResult


async def persist_event(session: AsyncSession, event: EventEnvelope) -> None:
    row = EventLogRow(
        event_id=event.event_id,
        event_family=event.event_family.value,
        event_type=event.event_type,
        event_time=event.event_time,
        processing_time=event.processing_time,
        correlation_id=event.correlation_id,
        symbol=event.symbol,
        timeframe=event.timeframe,
        mode=event.mode,
        revision_id=event.revision_id,
        experiment_id=event.experiment_id,
        causation_id=event.causation_id,
        payload=event.payload,
    )
    session.add(row)


async def persist_validation_result(
    session: AsyncSession,
    result: ValidationResult,
    *,
    revision_id: str | None = None,
    experiment_id: str | None = None,
) -> None:
    now = datetime.now(UTC)
    rev = revision_id or result.revision_id
    exp = experiment_id or result.experiment_id
    session.add(
        BacktestRunRow(
            run_id=result.run_id,
            symbol=result.config.symbol,
            timeframe=result.config.timeframe,
            config={
                "start": result.config.start.isoformat(),
                "end": result.config.end.isoformat(),
                "revision_id": rev,
                "experiment_id": exp,
            },
            metrics={
                "engine": result.engine_metrics,
                "outcome": result.outcome_metrics,
            },
            started_at=result.config.start,
            completed_at=now,
        )
    )

    seen_feature_sets: set[str] = set()
    for cycle in result.cycles:
        fs = cycle.feature_set
        if fs.feature_set_id not in seen_feature_sets:
            if await session.get(FeatureSetRow, fs.feature_set_id) is None:
                session.add(
                    FeatureSetRow(
                        feature_set_id=fs.feature_set_id,
                        feature_version=fs.feature_version,
                        config_hash=fs.config_hash,
                        payload=fs.model_dump(mode="json"),
                        created_at=fs.processing_time,
                    )
                )
            seen_feature_sets.add(fs.feature_set_id)

        snap = cycle.snapshot
        if await session.get(StateSnapshotRow, snap.snapshot_id) is None:
            session.add(
                StateSnapshotRow(
                    snapshot_id=snap.snapshot_id,
                    correlation_id=cycle.correlation_id,
                    portfolio=snap.portfolio.model_dump(mode="json"),
                    risk=snap.risk.model_dump(mode="json"),
                    version=snap.version,
                    created_at=snap.created_at,
                )
            )

    for event in result.events:
        if event.event_type == ExecutionEventType.POSITION_CLOSED:
            trade_id = f"trade_{event.payload['fill_id']}"
            if await session.get(SimulatedTradeRow, trade_id) is not None:
                continue
            session.add(
                SimulatedTradeRow(
                    trade_id=trade_id,
                    run_id=result.run_id,
                    position_id=event.payload["position_id"],
                    correlation_id=event.correlation_id,
                    symbol=event.symbol,
                    pnl=float(event.payload["pnl"]),
                    exit_reason=event.payload["exit_reason"],
                    payload=event.payload,
                )
            )

    await session.commit()
