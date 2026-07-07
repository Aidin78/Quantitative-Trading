from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.replay.engine import ReplayEngine

router = APIRouter(prefix="/replay", tags=["replay"], dependencies=[Depends(get_current_user)])


@router.post("/cycle/{correlation_id}")
async def replay_cycle(correlation_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    engine = await ReplayEngine.from_db(db, correlation_id)
    result = engine.replay_cycle(correlation_id)
    if not result.events:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return {
        "correlation_id": correlation_id,
        "timeline": result.timeline,
        "families_present": [f.value for f in result.families_present],
    }


@router.get("/cycle/{correlation_id}/timeline")
async def replay_timeline(correlation_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    return await replay_cycle(correlation_id, db)
