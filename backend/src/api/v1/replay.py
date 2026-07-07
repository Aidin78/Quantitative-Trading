from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.replay.engine import ReplayEngine
from src.replay.graph import build_causal_graph
from src.replay.reexecutor import ReExecuteError

router = APIRouter(prefix="/replay", tags=["replay"], dependencies=[Depends(get_current_user)])


def _serialize_result(result) -> dict:  # noqa: ANN001
    payload = {
        "correlation_id": result.correlation_id,
        "mode": result.mode,
        "timeline": result.timeline,
        "families_present": [f.value for f in result.families_present],
        "causal_graph": result.causal_graph,
    }
    if result.decision_diff is not None:
        payload["decision_diff"] = result.decision_diff
    if result.feature_drift is not None:
        payload["feature_drift"] = result.feature_drift
    return payload


async def _run_replay(
    correlation_id: str,
    db: AsyncSession,
    *,
    mode: Literal["strict", "re_execute"],
    revision_id: str | None,
) -> dict:
    engine = await ReplayEngine.from_db(db, correlation_id)
    try:
        if mode == "re_execute":
            result = await engine.replay_cycle_async(
                db,
                correlation_id,
                mode=mode,
                revision_id=revision_id,
            )
        else:
            result = engine.replay_cycle(correlation_id, mode=mode)
    except ReExecuteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not result.events:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return _serialize_result(result)


@router.post("/cycle/{correlation_id}")
async def replay_cycle(
    correlation_id: str,
    db: AsyncSession = Depends(get_db),
    mode: Literal["strict", "re_execute"] = Query("strict"),
    revision_id: str | None = Query(None),
) -> dict:
    return await _run_replay(correlation_id, db, mode=mode, revision_id=revision_id)


@router.get("/cycle/{correlation_id}/timeline")
async def replay_timeline(
    correlation_id: str,
    db: AsyncSession = Depends(get_db),
    mode: Literal["strict", "re_execute"] = Query("strict"),
    revision_id: str | None = Query(None),
) -> dict:
    return await _run_replay(correlation_id, db, mode=mode, revision_id=revision_id)


@router.get("/cycle/{correlation_id}/graph")
async def replay_graph(correlation_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    engine = await ReplayEngine.from_db(db, correlation_id)
    events = [e for e in engine._events if e.correlation_id == correlation_id]  # noqa: SLF001
    if not events:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return build_causal_graph(events)
