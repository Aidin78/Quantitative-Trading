from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.services.live_service import get_live_manager
from src.core.settings import load_app_yaml_config
from src.governance.experiment_store import (
    create_experiment,
    delete_experiment,
    delete_experiments,
    get_experiment,
    list_experiments,
)
from src.governance.revision_store import ensure_current_revision

router = APIRouter(
    prefix="/experiments", tags=["experiments"], dependencies=[Depends(get_current_user)]
)


class ExperimentCreateRequest(BaseModel):
    name: str
    revision_id: str | None = None
    mode: str = "validation"
    description: str = ""
    hypothesis: str | None = None
    symbols: list[str] | None = None
    timeframes: list[str] | None = None


class ExperimentBulkDeleteRequest(BaseModel):
    experiment_ids: list[str]


def _active_experiment_id() -> str | None:
    mgr = get_live_manager()
    if mgr.state.status != "running":
        return None
    return mgr.state.experiment_id


def _blocked_ids(experiment_ids: list[str]) -> list[str]:
    active = _active_experiment_id()
    if not active:
        return []
    return [eid for eid in experiment_ids if eid == active]


@router.get("")
async def list_all_experiments(
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
) -> dict:
    items = await list_experiments(db, limit=limit)
    return {
        "items": [e.model_dump(mode="json") for e in items],
        "total": len(items),
    }


@router.post("")
async def create_experiment_route(
    body: ExperimentCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    revision_id = body.revision_id
    if not revision_id:
        revision = await ensure_current_revision(db, label=body.name)
        revision_id = revision.revision_id
    app = load_app_yaml_config()
    experiment = await create_experiment(
        db,
        revision_id=revision_id,
        name=body.name,
        mode=body.mode,  # type: ignore[arg-type]
        symbols=tuple(body.symbols) if body.symbols else app.default_symbols,
        timeframes=tuple(body.timeframes) if body.timeframes else app.timeframes,
        description=body.description,
        hypothesis=body.hypothesis,
    )
    await db.commit()
    return experiment.model_dump(mode="json")


@router.post("/bulk-delete")
async def bulk_delete_experiments(
    body: ExperimentBulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not body.experiment_ids:
        raise HTTPException(status_code=400, detail="experiment_ids must not be empty")
    blocked = _blocked_ids(body.experiment_ids)
    deleted, not_found, skipped = await delete_experiments(
        db,
        body.experiment_ids,
        skip_ids=frozenset(blocked),
    )
    await db.commit()
    return {
        "deleted": deleted,
        "not_found": not_found,
        "blocked": skipped,
        "deleted_count": len(deleted),
    }


@router.delete("/{experiment_id}")
async def delete_experiment_route(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if experiment_id in _blocked_ids([experiment_id]):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete experiment while it is active in live/paper mode",
        )
    removed = await delete_experiment(db, experiment_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Experiment not found")
    await db.commit()
    return {"deleted": experiment_id}


@router.get("/{experiment_id}")
async def get_experiment_route(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    experiment = await get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment.model_dump(mode="json")
