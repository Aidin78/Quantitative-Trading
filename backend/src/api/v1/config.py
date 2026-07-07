from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.governance.revision_store import get_revision, list_revisions

router = APIRouter(prefix="/config", tags=["config"], dependencies=[Depends(get_current_user)])


@router.get("/revisions")
async def get_config_revisions(
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
) -> dict:
    revisions = await list_revisions(db, limit=limit)
    return {
        "items": [r.model_dump(mode="json") for r in revisions],
        "total": len(revisions),
    }


@router.get("/revisions/{revision_id}")
async def get_config_revision(revision_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    revision = await get_revision(db, revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Revision not found")
    return revision.model_dump(mode="json")
