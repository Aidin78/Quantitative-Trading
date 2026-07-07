from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.db.repositories.decision import DecisionFilters, get_decision, list_decisions

router = APIRouter(prefix="/signals", tags=["signals"], dependencies=[Depends(get_current_user)])


@router.get("")
async def list_signals(
    db: AsyncSession = Depends(get_db),
    symbol: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    filters = DecisionFilters(symbol=symbol, result="approved")
    items, total = await list_decisions(db, filters=filters, page=page, limit=limit)
    signals = [
        {
            "id": item["id"],
            "decision_id": item["id"],
            "symbol": item["symbol"],
            "side": item["side"],
            "confidence": item["confidence"],
            "timestamp": item["timestamp"],
        }
        for item in items
    ]
    return {"items": signals, "total": total, "page": page, "limit": limit}


@router.get("/{signal_id}")
async def get_signal(signal_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    detail = await get_decision(db, signal_id)
    if detail is None or detail["result"] != "approved":
        raise HTTPException(status_code=404, detail="Signal not found")
    return detail
