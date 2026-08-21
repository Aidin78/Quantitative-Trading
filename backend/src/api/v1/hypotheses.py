from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.services.hypothesis_generation_service import (
    hypothesis_generation_jobs,
    start_hypothesis_generation,
)
from src.governance.hypothesis_store import (
    create_hypothesis,
    get_hypothesis,
    link_hypothesis_to_experiment,
    list_hypotheses,
    resolve_hypothesis,
    search_similar_hypotheses,
)

router = APIRouter(
    prefix="/hypotheses", tags=["hypotheses"], dependencies=[Depends(get_current_user)]
)


class HypothesisCreateRequest(BaseModel):
    observation: str
    statement: str
    expected_effect: str
    proposed_change: str
    source_experiment_run_id: str | None = None
    created_by: str = "system"


class HypothesisLinkRequest(BaseModel):
    experiment_id: str


class HypothesisResolveRequest(BaseModel):
    confirmed: bool


class SimilarHypothesesRequest(BaseModel):
    proposed_change: str
    min_overlap: float = 0.5


class HypothesisGenerateRequest(BaseModel):
    run_id: str


@router.get("")
async def list_all_hypotheses(
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    limit: int = 50,
) -> dict:
    items = await list_hypotheses(db, status=status, limit=limit)
    return {
        "items": [h.model_dump(mode="json") for h in items],
        "total": len(items),
    }


@router.post("")
async def create_hypothesis_route(
    body: HypothesisCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    hypothesis = await create_hypothesis(
        db,
        observation=body.observation,
        statement=body.statement,
        expected_effect=body.expected_effect,
        proposed_change=body.proposed_change,
        source_experiment_run_id=body.source_experiment_run_id,
        created_by=body.created_by,
    )
    await db.commit()
    return hypothesis.model_dump(mode="json")


@router.post("/search")
async def search_hypotheses_route(
    body: SimilarHypothesesRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await search_similar_hypotheses(db, body.proposed_change, min_overlap=body.min_overlap)
    return {
        "items": [h.model_dump(mode="json") for h in items],
        "total": len(items),
    }


@router.post("/generate")
async def generate_hypothesis_route(body: HypothesisGenerateRequest) -> dict:
    """Kicks off a background job that reads the given backtest run's
    failure_summary and drafts a hypothesis with Claude (created_by="llm").
    Never runs automatically -- only in response to this explicit call.
    Poll GET /hypotheses/generate/{job_id} for status; the resulting
    hypothesis is a normal draft (status="open") that still goes through the
    same human review / experiment path as any other hypothesis.
    """
    job = start_hypothesis_generation(body.run_id)
    return {"job_id": job.id, "status": job.status}


@router.get("/generate/{job_id}")
async def get_hypothesis_generation_job_route(job_id: str) -> dict:
    job = hypothesis_generation_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    return {
        "job_id": job.id,
        "run_id": job.run_id,
        "status": job.status,
        "hypothesis_id": job.hypothesis_id,
        "error": job.error,
    }


@router.get("/{hypothesis_id}")
async def get_hypothesis_route(
    hypothesis_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    hypothesis = await get_hypothesis(db, hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return hypothesis.model_dump(mode="json")


@router.post("/{hypothesis_id}/link")
async def link_hypothesis_route(
    hypothesis_id: str,
    body: HypothesisLinkRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    hypothesis = await link_hypothesis_to_experiment(
        db, hypothesis_id, experiment_id=body.experiment_id
    )
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    await db.commit()
    return hypothesis.model_dump(mode="json")


@router.post("/{hypothesis_id}/resolve")
async def resolve_hypothesis_route(
    hypothesis_id: str,
    body: HypothesisResolveRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    hypothesis = await resolve_hypothesis(db, hypothesis_id, confirmed=body.confirmed)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    await db.commit()
    return hypothesis.model_dump(mode="json")
