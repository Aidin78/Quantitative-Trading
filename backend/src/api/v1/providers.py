from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.api.services.config_service import list_provider_configs, write_provider_config

router = APIRouter(
    prefix="/providers", tags=["providers"], dependencies=[Depends(get_current_user)]
)


class ProviderPatch(BaseModel):
    enabled: bool | None = None
    weight: float | None = Field(default=None, ge=0.0)
    params: dict | None = None


@router.get("")
async def get_providers() -> dict:
    items = list_provider_configs()
    enriched = []
    for item in items:
        enriched.append(
            {
                **item,
                "name": item["provider_id"].replace("_", " ").title(),
                "required_features": ["ema_cross_bullish"]
                if item["provider_id"] == "ema_crossover"
                else ["rsi_14"],
            }
        )
    return {"items": enriched}


@router.patch("/{provider_id}")
async def patch_provider(provider_id: str, body: ProviderPatch) -> dict:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = write_provider_config(provider_id, patch)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return updated
