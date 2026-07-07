from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.core.settings import load_app_yaml_config
from src.governance.experiment_store import create_experiment, get_experiment, list_experiments
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


@router.get("/{experiment_id}")
async def get_experiment_route(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    experiment = await get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment.model_dump(mode="json")
