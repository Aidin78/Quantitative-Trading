from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.api.services.config_service import (
    apply_baseline_provider_setup,
    list_provider_configs,
    reset_all_provider_configs,
    reset_provider_config,
    write_provider_config,
)
from src.providers.metadata import get_provider_metadata, metadata_to_dict

router = APIRouter(
    prefix="/providers", tags=["providers"], dependencies=[Depends(get_current_user)]
)


class ProviderPatch(BaseModel):
    enabled: bool | None = None
    weight: float | None = Field(default=None, ge=0.0)
    params: dict | None = None


def _enrich_provider(item: dict) -> dict:
    meta = get_provider_metadata(item["provider_id"])
    enriched = {
        **item,
        "name": item["provider_id"].replace("_", " ").title(),
    }
    if meta is not None:
        enriched.update(metadata_to_dict(meta))
    else:
        enriched["required_features"] = []
        enriched["summary"] = ""
        enriched["rules"] = []
        enriched["default_config"] = {
            "enabled": item.get("enabled", True),
            "weight": item.get("weight", 1.0),
            "params": item.get("params", {}),
        }
        enriched["param_fields"] = []
    return enriched


@router.get("")
async def get_providers() -> dict:
    items = [_enrich_provider(item) for item in list_provider_configs()]
    return {"items": items}


@router.post("/reset-all")
async def reset_all_providers() -> dict:
    try:
        items = reset_all_provider_configs()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"items": [_enrich_provider(item) for item in items]}


@router.post("/baseline")
async def apply_baseline() -> dict:
    """Reset EMA + RSI + MACD to factory params and enable all three."""
    try:
        items = apply_baseline_provider_setup()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"items": [_enrich_provider(item) for item in items]}


@router.get("/{provider_id}")
async def get_provider(provider_id: str) -> dict:
    for item in list_provider_configs():
        if item["provider_id"] == provider_id:
            return _enrich_provider(item)
    raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")


@router.patch("/{provider_id}")
async def patch_provider(provider_id: str, body: ProviderPatch) -> dict:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = write_provider_config(provider_id, patch)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _enrich_provider(updated)


@router.post("/{provider_id}/reset")
async def reset_provider(provider_id: str) -> dict:
    try:
        updated = reset_provider_config(provider_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _enrich_provider(updated)
