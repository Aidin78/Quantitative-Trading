from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.db.repositories.decision import (
    DASHBOARD_MODES,
    DecisionFilters,
    get_decision,
    list_decisions,
)

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
    scope: str = Query("live", pattern="^(live|all)$"),
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
        modes=None if scope == "all" else DASHBOARD_MODES,
    )
    items, total = await list_decisions(db, filters=filters, page=page, limit=limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/export")
async def export_decisions(
    db: AsyncSession = Depends(get_db),
    format: str = Query("csv"),
    scope: str = Query("live", pattern="^(live|all)$"),
    limit: int = Query(1000, ge=1, le=5000),
) -> StreamingResponse:
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only csv format supported")
    filters = DecisionFilters(modes=None if scope == "all" else DASHBOARD_MODES)
    items, _ = await list_decisions(db, filters=filters, limit=limit)
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "id",
            "symbol",
            "timeframe",
            "result",
            "side",
            "confidence",
            "rejection_reason",
            "correlation_id",
            "revision_id",
            "experiment_id",
            "timestamp",
        ],
    )
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "id": item.get("id"),
                "symbol": item.get("symbol"),
                "timeframe": item.get("timeframe"),
                "result": item.get("result"),
                "side": item.get("side"),
                "confidence": item.get("confidence"),
                "rejection_reason": item.get("rejection_reason"),
                "correlation_id": item.get("correlation_id"),
                "revision_id": item.get("revision_id"),
                "experiment_id": item.get("experiment_id"),
                "timestamp": item.get("timestamp"),
            }
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=decisions.csv"},
    )


@router.get("/{decision_id}")
async def get_decision_detail(decision_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    detail = await get_decision(db, decision_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return detail
