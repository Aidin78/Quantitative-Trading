from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.governance.candidate_store import (
    create_candidate,
    get_candidate,
    list_candidate_evaluations,
    list_candidates,
    promote_candidate,
)

router = APIRouter(
    prefix="/candidates", tags=["candidates"], dependencies=[Depends(get_current_user)]
)


class CandidateCreateRequest(BaseModel):
    experiment_id: str
    hypothesis_id: str | None = None
    parent_candidate_id: str | None = None


class CandidatePromoteRequest(BaseModel):
    to_state: str


@router.get("")
async def list_all_candidates(
    db: AsyncSession = Depends(get_db),
    state: str | None = None,
    limit: int = 50,
) -> dict:
    items = await list_candidates(db, state=state, limit=limit)
    return {
        "items": [c.model_dump(mode="json") for c in items],
        "total": len(items),
    }


@router.post("")
async def create_candidate_route(
    body: CandidateCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    candidate = await create_candidate(
        db,
        experiment_id=body.experiment_id,
        hypothesis_id=body.hypothesis_id,
        parent_candidate_id=body.parent_candidate_id,
    )
    await db.commit()
    return candidate.model_dump(mode="json")


@router.get("/{candidate_id}")
async def get_candidate_route(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    candidate = await get_candidate(db, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate.model_dump(mode="json")


@router.get("/{candidate_id}/evaluations")
async def list_candidate_evaluations_route(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if await get_candidate(db, candidate_id) is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    evaluations = await list_candidate_evaluations(db, candidate_id)
    return {
        "items": [e.model_dump(mode="json") for e in evaluations],
        "total": len(evaluations),
    }


@router.post("/{candidate_id}/promote")
async def promote_candidate_route(
    candidate_id: str,
    body: CandidatePromoteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        candidate = await promote_candidate(db, candidate_id, to_state=body.to_state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    await db.commit()
    return candidate.model_dump(mode="json")
