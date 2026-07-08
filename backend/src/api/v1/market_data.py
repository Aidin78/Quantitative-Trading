from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.api.services.validation_runner import format_validation_error
from src.core.exceptions import DataProviderError
from src.core.settings import get_settings, load_app_yaml_config
from src.data.market_cache import (
    csv_summary,
    download_csv,
    list_cache_entries,
    resolve_cache_file,
    resolve_range,
)

router = APIRouter(
    prefix="/market-data",
    tags=["market-data"],
    dependencies=[Depends(get_current_user)],
)


class MarketDataDownloadRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    months: int | None = Field(default=3, ge=1, le=24)
    force: bool = False


@router.get("/cache")
async def market_data_cache() -> dict:
    return {"items": list_cache_entries()}


@router.post("/download")
async def market_data_download(body: MarketDataDownloadRequest) -> dict:
    app = load_app_yaml_config()
    settings = get_settings()
    symbol = body.symbol or app.default_symbols[0]
    timeframe = body.timeframe or app.timeframes[0]
    start, end = resolve_range(
        start_date=body.start_date,
        end_date=body.end_date,
        months=body.months if body.start_date is None else None,
    )
    try:
        path, refreshed = await download_csv(
            exchange_id=settings.exchange_id,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            force=body.force,
        )
    except DataProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail=format_validation_error(exc),
        ) from exc
    summary = csv_summary(path)
    return {
        "filename": path.name,
        "path": str(path),
        "exchange_id": settings.exchange_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "refreshed": refreshed,
        **summary,
    }


@router.get("/cache/{filename}/file")
async def market_data_cache_file(filename: str) -> FileResponse:
    try:
        path = resolve_cache_file(filename)
    except DataProviderError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type="text/csv",
        filename=path.name,
    )
