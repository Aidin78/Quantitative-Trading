from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.context import MarketContext
from src.core.contracts.decision import Decision, DecisionLog, DecisionResult
from src.core.contracts.event import EventEnvelope, EventFamily
from src.core.contracts.rationale import ProviderRationale
from src.core.contracts.signal import StrategySignal
from src.core.contracts.state import PortfolioState, RiskState, StateSnapshot
from src.db.models import StateSnapshotRow
from src.engine.config import (
    AggregationConfig,
    EngineConfig,
    FilterConfig,
    RiskConfig,
    load_engine_config,
)
from src.engine.decision_engine import DecisionEngine
from src.events.envelopes import DecisionEventType, MarketEventType, SignalEventType
from src.features.config import load_features_config
from src.features.drift import compare_features
from src.governance.revision_store import compute_config_revision, get_revision
from src.replay.diff import DecisionDiff, build_decision_diff
from src.replay.feature_rebuild import rebuild_indicators


class ReExecuteError(ValueError):
    pass


def _find_event(events: list[EventEnvelope], event_type: str) -> EventEnvelope | None:
    for event in events:
        if event.event_type == event_type:
            return event
    return None


def _signals_from_events(events: list[EventEnvelope]) -> list[StrategySignal]:
    signals: list[StrategySignal] = []
    for event in events:
        if event.event_family != EventFamily.SIGNAL:
            continue
        if event.event_type != SignalEventType.PROVIDER_OPINION:
            continue
        payload = event.payload
        rationale_raw = payload.get("rationale") or {}
        signals.append(
            StrategySignal(
                provider_id=str(payload["provider_id"]),
                symbol=event.symbol,
                side=payload["side"],
                confidence=float(payload["confidence"]),
                rationale=ProviderRationale(**rationale_raw),
                feature_set_id=str(
                    _find_event(events, MarketEventType.FEATURE_SET_BUILT).payload.get(
                        "feature_set_id", ""
                    )
                    if _find_event(events, MarketEventType.FEATURE_SET_BUILT)
                    else ""
                ),
                timeframe=event.timeframe,
                event_time=event.event_time,
            )
        )
    return signals


async def _load_snapshot(session: AsyncSession, snapshot_id: str) -> StateSnapshot:
    row = await session.get(StateSnapshotRow, snapshot_id)
    if row is None:
        raise ReExecuteError(f"State snapshot not found: {snapshot_id}")
    return StateSnapshot(
        snapshot_id=row.snapshot_id,
        portfolio=PortfolioState(**row.portfolio),
        risk=RiskState(**row.risk),
        version=row.version,
        created_at=row.created_at,
    )


async def _engine_for_revision(
    session: AsyncSession,
    revision_id: str | None,
) -> DecisionEngine:
    if not revision_id:
        return DecisionEngine(load_engine_config())
    revision = await get_revision(session, revision_id)
    if revision is None:
        return DecisionEngine(load_engine_config())
    engine_raw = revision.config_bundle.get("engine", {})
    engine = engine_raw.get("engine", engine_raw)
    cfg = EngineConfig(
        aggregation=AggregationConfig(**engine["aggregation"]),
        filter=FilterConfig(
            min_atr_pct=engine["filter"]["min_atr_pct"],
            allowed_sessions=tuple(engine["filter"]["allowed_sessions"]),
        ),
        risk=RiskConfig(**engine["risk"]),
    )
    return DecisionEngine(cfg)


async def re_execute_cycle(
    session: AsyncSession,
    events: list[EventEnvelope],
    *,
    revision_id: str | None = None,
) -> tuple[Decision, DecisionDiff, dict | None]:
    if not events:
        raise ReExecuteError("No events for cycle")
    correlation_id = events[0].correlation_id
    made = _find_event(events, DecisionEventType.DECISION_MADE)
    context_event = _find_event(events, MarketEventType.MARKET_CONTEXT_DERIVED)
    feature_event = _find_event(events, MarketEventType.FEATURE_SET_BUILT)
    if made is None or context_event is None or feature_event is None:
        raise ReExecuteError(
            "Cycle missing required events for re-execute "
            "(DECISION_MADE, MARKET_CONTEXT_DERIVED, FEATURE_SET_BUILT)"
        )
    snapshot = await _load_snapshot(session, made.payload["state_snapshot_id"])
    signals = _signals_from_events(events)
    if not signals:
        raise ReExecuteError("No provider opinions found for re-execute")
    context = MarketContext(**context_event.payload)
    original_log = DecisionLog(**made.payload["decision_log"])
    original = Decision(
        decision_id=made.payload["decision_id"],
        result=DecisionResult(value=made.payload["result"]),
        decision_log=original_log,
        correlation_id=correlation_id,
        event_time=made.event_time,
        decision_time=made.processing_time,
        revision_id=made.revision_id,
        experiment_id=made.experiment_id,
    )
    engine = await _engine_for_revision(session, revision_id)
    reexecuted = engine.process(
        signals,
        context,
        snapshot,
        correlation_id=correlation_id,
        event_time=made.event_time,
        decision_time=made.processing_time,
        revision_id=revision_id or made.revision_id,
        experiment_id=made.experiment_id,
    )
    diff = build_decision_diff(correlation_id, original, reexecuted, revision_id=revision_id)
    feature_drift = _detect_feature_drift(feature_event)
    return reexecuted, diff, feature_drift


def _detect_feature_drift(
    feature_event: EventEnvelope,
    *,
    csv_path: str | None = None,
) -> dict:
    stored_indicators = feature_event.payload.get("indicators") or {}
    stored_flags = feature_event.payload.get("flags") or {}
    stored_hash = feature_event.payload.get("config_hash", "")
    current = compute_config_revision()
    features_config, features_hash = load_features_config()

    # Always rebuild with current disk features config (indicator deltas when
    # hashes diverge). Optimizer synthetic hashes are out of scope.
    rebuilt = rebuild_indicators(
        feature_event,
        csv_path=csv_path,
        features_config=features_config,
        config_hash=features_hash,
    )
    if rebuilt is not None:
        drift = compare_features(
            stored_indicators,
            rebuilt["indicators"],
            stored_flags=stored_flags,
            rebuilt_flags=rebuilt.get("flags") or {},
        )
    else:
        drift = {
            "detected": False,
            "drift_count": 0,
            "drifts": [],
            "rebuild_skipped": True,
            "reason": "ohlcv_unavailable",
        }

    drift["drifted_features"] = [
        str(item["key"]) for item in drift.get("drifts", []) if item.get("key") is not None
    ]

    if stored_hash and stored_hash != current.features_config_hash:
        return {
            **drift,
            "detected": True,
            "config_hash_stored": stored_hash,
            "config_hash_current": current.features_config_hash,
            "reason": drift.get("reason") or "config_hash_mismatch",
        }
    return drift
