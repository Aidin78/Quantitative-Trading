from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_current_user

router = APIRouter(
    prefix="/validation", tags=["validation"], dependencies=[Depends(get_current_user)]
)
