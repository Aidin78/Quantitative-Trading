from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.services.config_service import read_engine_config, write_engine_config
from src.db.repositories.decision import compute_engine_stats
from src.governance.revision_store import compute_config_revision, save_revision

router = APIRouter(prefix="/engine", tags=["engine"], dependencies=[Depends(get_current_user)])


class EngineConfigPatch(BaseModel):
    aggregation: dict | None = None
    filter: dict | None = None
    risk: dict | None = None


@router.get("/config")
async def get_engine_config() -> dict:
    cfg = read_engine_config()
    return {"engine": cfg.model_dump()}


@router.patch("/config")
async def patch_engine_config(
    body: EngineConfigPatch,
    db: AsyncSession = Depends(get_db),
) -> dict:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    cfg = write_engine_config(patch)
    revision = compute_config_revision(label="engine_patch")
    await save_revision(db, revision)
    await db.commit()
    return {"engine": cfg.model_dump(), "revision_id": revision.revision_id}


@router.get("/stats")
async def get_engine_stats(db: AsyncSession = Depends(get_db)) -> dict:
    return await compute_engine_stats(db)
