from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.event import EventEnvelope, EventFamily
from src.db.models import DecisionRecordRow, EventLogRow, FeatureSetRow
from src.events.envelopes import DecisionEventType, MarketEventType, SignalEventType


async def persist_decision_from_event(session: AsyncSession, event: EventEnvelope) -> None:
    if event.event_type != DecisionEventType.DECISION_MADE:
        return
    payload = event.payload
    session.add(
        DecisionRecordRow(
            decision_id=payload["decision_id"],
            correlation_id=event.correlation_id,
            result=payload["result"],
            state_snapshot_id=payload["state_snapshot_id"],
            decision_log=payload["decision_log"],
            created_at=event.event_time,
        )
    )


async def persist_feature_set_from_event(session: AsyncSession, event: EventEnvelope) -> None:
    if event.event_type != MarketEventType.FEATURE_SET_BUILT:
        return
    payload = event.payload
    feature_set_id = payload["feature_set_id"]
    existing = await session.get(FeatureSetRow, feature_set_id)
    if existing is not None:
        return
    session.add(
        FeatureSetRow(
            feature_set_id=feature_set_id,
            feature_version=payload["feature_version"],
            config_hash=payload["config_hash"],
            payload=payload,
            created_at=event.event_time,
        )
    )


class DecisionFilters:
    def __init__(
        self,
        *,
        symbol: str | None = None,
        result: str | None = None,
        side: str | None = None,
        rejection_reason: str | None = None,
        provider: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        self.symbol = symbol
        self.result = result
        self.side = side
        self.rejection_reason = rejection_reason
        self.provider = provider
        self.start_date = start_date
        self.end_date = end_date


async def list_decisions(
    session: AsyncSession,
    *,
    filters: DecisionFilters | None = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[dict], int]:
    filters = filters or DecisionFilters()
    base = select(DecisionRecordRow).order_by(DecisionRecordRow.created_at.desc())
    if filters.result:
        base = base.where(DecisionRecordRow.result == filters.result)
    if filters.start_date:
        base = base.where(DecisionRecordRow.created_at >= filters.start_date)
    if filters.end_date:
        base = base.where(DecisionRecordRow.created_at <= filters.end_date)

    offset = max(page - 1, 0) * limit
    rows = (await session.execute(base)).scalars().all()

    items: list[dict] = []
    for row in rows:
        meta = await _decision_meta(session, row)
        events = await _events_for_correlation(session, row.correlation_id)
        summary = _row_to_summary(row, meta, events)
        if not _matches_filters(summary, row, filters, events):
            continue
        items.append(summary)

    total = len(items)
    return items[offset : offset + limit], total


def _matches_filters(
    summary: dict,
    row: DecisionRecordRow,
    filters: DecisionFilters,
    events: list[EventEnvelope],
) -> bool:
    if filters.symbol and summary.get("symbol") != filters.symbol:
        return False
    if filters.side and summary.get("side") != filters.side:
        return False
    if filters.provider and filters.provider not in summary.get("provider_ids", []):
        return False
    if filters.rejection_reason:
        reason = summary.get("rejection_reason") or _extract_rejection_reason(row.decision_log)
        if reason != filters.rejection_reason:
            return False
    return True


async def get_decision(session: AsyncSession, decision_id: str) -> dict | None:
    row = await session.get(DecisionRecordRow, decision_id)
    if row is None:
        return None
    meta = await _decision_meta(session, row)
    events = await _events_for_correlation(session, row.correlation_id)
    provider_signals = [
        e.payload
        for e in events
        if e.event_family == EventFamily.SIGNAL and e.event_type == SignalEventType.PROVIDER_OPINION
    ]
    feature_snapshot = await _feature_snapshot(session, row.correlation_id, events)
    market_context = _market_context(events)
    outcome = _outcome_event(events, decision_id)
    summary = _row_to_summary(row, meta, events)
    rejection_reason = (
        outcome.get("rejection_reason") if outcome else summary.get("rejection_reason")
    )
    rejection_stage = outcome.get("rejection_stage") if outcome else summary.get("rejection_stage")
    final_signal = outcome.get("final_signal") if outcome else None
    return {
        **summary,
        "rejection_reason": rejection_reason,
        "rejection_stage": rejection_stage,
        "final_signal": final_signal,
        "feature_snapshot": feature_snapshot,
        "market_context": market_context,
        "provider_signals": provider_signals,
        "decision_log": row.decision_log,
        "explainability": {
            "summary": _explain_summary(row, rejection_reason),
            "state_snapshot_id": row.state_snapshot_id,
            "correlation_id": row.correlation_id,
            "causal_chain_url": f"/api/v1/replay/cycle/{row.correlation_id}/timeline",
        },
        "event_time": row.created_at.isoformat(),
        "decision_time": row.created_at.isoformat(),
    }


async def compute_engine_stats(session: AsyncSession) -> dict:
    total = (
        await session.execute(select(func.count()).select_from(DecisionRecordRow))
    ).scalar_one()
    if total == 0:
        return {
            "decisions_today": 0,
            "approval_rate": 0.0,
            "rejection_breakdown": {},
            "active_providers": 0,
            "feature_set_version": "v1",
        }
    approved = (
        await session.execute(select(func.count()).where(DecisionRecordRow.result == "approved"))
    ).scalar_one()
    rows = (await session.execute(select(DecisionRecordRow))).scalars().all()
    breakdown: dict[str, int] = {}
    for row in rows:
        if row.result != "rejected":
            continue
        log = row.decision_log
        reason = _extract_rejection_reason(log)
        breakdown[reason] = breakdown.get(reason, 0) + 1
    provider_ids: set[str] = set()
    for row in rows:
        for sig in row.decision_log.get("provider_signals", []):
            provider_ids.add(sig.get("provider_id", ""))
    provider_ids.discard("")
    return {
        "decisions_today": total,
        "approval_rate": approved / total if total else 0.0,
        "rejection_breakdown": breakdown,
        "active_providers": len(provider_ids),
        "feature_set_version": "v1",
    }


async def _decision_meta(session: AsyncSession, row: DecisionRecordRow) -> dict:
    stmt = (
        select(EventLogRow)
        .where(EventLogRow.correlation_id == row.correlation_id)
        .where(EventLogRow.event_type == DecisionEventType.DECISION_MADE)
        .limit(1)
    )
    event_row = (await session.execute(stmt)).scalar_one_or_none()
    if event_row:
        return {"symbol": event_row.symbol, "timeframe": event_row.timeframe}
    stmt2 = select(EventLogRow).where(EventLogRow.correlation_id == row.correlation_id).limit(1)
    any_row = (await session.execute(stmt2)).scalar_one_or_none()
    if any_row:
        return {"symbol": any_row.symbol, "timeframe": any_row.timeframe}
    return {"symbol": "UNKNOWN", "timeframe": "1h"}


async def _events_for_correlation(
    session: AsyncSession, correlation_id: str
) -> list[EventEnvelope]:
    from src.db.repositories.event_log import fetch_events_by_correlation

    return await fetch_events_by_correlation(session, correlation_id)


async def _feature_snapshot(
    session: AsyncSession,
    correlation_id: str,
    events: list[EventEnvelope],
) -> dict | None:
    for event in events:
        if event.event_type == MarketEventType.FEATURE_SET_BUILT:
            return {
                "version": event.payload.get("feature_version"),
                "indicators": event.payload.get("indicators", {}),
                "flags": event.payload.get("flags", {}),
            }
    return None


def _market_context(events: list[EventEnvelope]) -> dict | None:
    from src.events.envelopes import MarketEventType

    for event in events:
        if event.event_type == MarketEventType.MARKET_CONTEXT_DERIVED:
            return event.payload
    return None


def _outcome_event(events: list[EventEnvelope], decision_id: str) -> dict | None:
    for event in events:
        if event.payload.get("decision_id") != decision_id:
            continue
        if event.event_type in (
            DecisionEventType.DECISION_APPROVED,
            DecisionEventType.DECISION_REJECTED,
        ):
            return event.payload
    return None


def _row_to_summary(
    row: DecisionRecordRow,
    meta: dict,
    events: list[EventEnvelope] | None = None,
) -> dict:
    log = row.decision_log
    provider_ids = [
        s.get("provider_id", "") for s in log.get("provider_signals", []) if s.get("provider_id")
    ]
    side = None
    confidence = None
    if row.result == "approved":
        agg = log.get("aggregation", {})
        side = agg.get("side")
        confidence = agg.get("confidence")
    outcome = _outcome_event(events or [], row.decision_id) if events else None
    rejection_reason = None
    rejection_stage = None
    if row.result == "rejected":
        rejection_reason = (outcome or {}).get("rejection_reason") or _extract_rejection_reason(log)
        rejection_stage = (outcome or {}).get("rejection_stage") or _extract_rejection_stage(log)
    return {
        "id": row.decision_id,
        "symbol": meta.get("symbol"),
        "timeframe": meta.get("timeframe"),
        "result": row.result,
        "side": side,
        "confidence": confidence,
        "rejection_reason": rejection_reason,
        "rejection_stage": rejection_stage,
        "provider_ids": provider_ids,
        "feature_set_version": "v1",
        "timestamp": row.created_at.isoformat(),
        "correlation_id": row.correlation_id,
    }


def _extract_rejection_stage(log: dict) -> str | None:
    mf = log.get("market_filter", {})
    if not mf.get("passed", True):
        return "market_filter"
    agg = log.get("aggregation", {})
    if agg.get("side") == "HOLD" or not agg.get("passed", True):
        return "aggregator"
    risk = log.get("risk_check", {})
    if not risk.get("passed", True):
        return "risk_manager"
    return None


def _extract_rejection_reason(log: dict) -> str:
    mf = log.get("market_filter", {})
    if not mf.get("passed", True):
        return mf.get("reason") or "market_filter"
    agg = log.get("aggregation", {})
    if agg.get("side") == "HOLD":
        return "insufficient_consensus"
    risk = log.get("risk_check", {})
    if not risk.get("passed", True):
        checks = risk.get("checks", [])
        if checks:
            return checks[0].get("check_name", "risk")
        return "risk"
    return "unknown"


def _explain_summary(row: DecisionRecordRow, rejection_reason: str | None) -> str:
    if row.result == "approved":
        count = len(row.decision_log.get("provider_signals", []))
        side = row.decision_log.get("aggregation", {}).get("side", "BUY")
        return f"Approved: {count} provider(s) agree {side}"
    stage = _extract_rejection_stage(row.decision_log)
    stage_text = f" at {stage}" if stage else ""
    return f"Rejected{stage_text}: {rejection_reason or 'unknown'}"
