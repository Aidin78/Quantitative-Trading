from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.services.live_service import get_live_manager
from src.db.models import EventLogRow
from src.events.envelopes import DecisionEventType
from src.governance.live_gate import LiveGovernanceGate

router = APIRouter(prefix="/live", tags=["live"], dependencies=[Depends(get_current_user)])


class LiveStartRequest(BaseModel):
    mode: Literal["paper", "live"] = "paper"
    symbol: str | None = None
    timeframe: str | None = None
    revision_id: str | None = None
    experiment_id: str | None = None


class LiveModeRequest(BaseModel):
    mode: Literal["paper", "live"]


@router.get("/status")
async def live_status() -> dict:
    return get_live_manager().status_dict()


@router.post("/start")
async def live_start(
    body: LiveStartRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    gate = LiveGovernanceGate()
    if not await gate.allow_start(db, body.revision_id):
        raise HTTPException(
            status_code=403,
            detail=(
                "Live start blocked: revision_id required "
                "with successful validation in production"
            ),
        )
    jobs: list[tuple[str, str]] | None = None
    if body.symbol and body.timeframe:
        jobs = [(body.symbol, body.timeframe)]
    try:
        return await get_live_manager().start(
            mode=body.mode,
            jobs=jobs,
            revision_id=body.revision_id,
            experiment_id=body.experiment_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stop")
async def live_stop() -> dict:
    return await get_live_manager().stop()


@router.post("/mode")
async def live_mode(body: LiveModeRequest) -> dict:
    try:
        return await get_live_manager().set_mode(body.mode)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/decision-log")
async def live_decision_log(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    stmt = (
        select(EventLogRow)
        .where(
            EventLogRow.event_type.in_(
                [DecisionEventType.DECISION_APPROVED, DecisionEventType.DECISION_REJECTED]
            )
        )
        .where(EventLogRow.mode.in_(["paper", "live"]))
        .order_by(EventLogRow.event_time.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "timestamp": row.event_time.isoformat(),
            "symbol": row.symbol,
            "timeframe": row.timeframe,
            "result": "approved"
            if row.event_type == DecisionEventType.DECISION_APPROVED
            else "rejected",
            "mode": row.mode,
            "correlation_id": row.correlation_id,
            "revision_id": row.revision_id,
            "experiment_id": row.experiment_id,
            "payload": row.payload,
        }
        for row in rows
    ]
    return {"items": items, "total": len(items)}
