from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.db.repositories.decision import DecisionFilters, get_decision, list_decisions

router = APIRouter(
    prefix="/decisions", tags=["decisions"], dependencies=[Depends(get_current_user)]
)


@router.get("")
async def list_all_decisions(
    db: AsyncSession = Depends(get_db),
    symbol: str | None = None,
    result: str | None = None,
    side: str | None = None,
    rejection_reason: str | None = None,
    provider: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    filters = DecisionFilters(
        symbol=symbol,
        result=result,
        side=side,
        rejection_reason=rejection_reason,
        provider=provider,
        start_date=start_date,
        end_date=end_date,
    )
    items, total = await list_decisions(db, filters=filters, page=page, limit=limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/{decision_id}")
async def get_decision_detail(decision_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    detail = await get_decision(db, decision_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return detail
