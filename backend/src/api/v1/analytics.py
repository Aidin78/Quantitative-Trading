from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics.queries import compute_heatmap, compute_overview
from src.api.deps import get_current_user, get_db

router = APIRouter(
    prefix="/analytics", tags=["analytics"], dependencies=[Depends(get_current_user)]
)


@router.get("/overview")
async def analytics_overview(
    db: AsyncSession = Depends(get_db),
    period: str = Query("30d"),
) -> dict:
    return await compute_overview(db, period=period)


@router.get("/heatmap")
async def analytics_heatmap(
    db: AsyncSession = Depends(get_db),
    period: str = Query("30d"),
) -> dict:
    return await compute_heatmap(db, period=period)
