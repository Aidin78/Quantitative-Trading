from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.auth import get_subject_from_token
from src.core.settings import get_settings
from src.db.session import get_session_factory

security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str:
    settings = get_settings()
    if not settings.auth_required:
        if credentials and credentials.credentials:
            subject = get_subject_from_token(credentials.credentials)
            if subject:
                return subject
        return "anonymous"
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    subject = get_subject_from_token(credentials.credentials)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return subject


async def get_ws_user(websocket: WebSocket) -> str:
    settings = get_settings()
    token = websocket.query_params.get("token")
    if not settings.auth_required:
        if token:
            subject = get_subject_from_token(token)
            if subject:
                return subject
        return "anonymous"
    if not token:
        await websocket.close(code=4401)
        raise HTTPException(status_code=401, detail="Missing token")
    subject = get_subject_from_token(token)
    if subject is None:
        await websocket.close(code=4401)
        raise HTTPException(status_code=401, detail="Invalid token")
    return subject


def get_session_factory_dep() -> async_sessionmaker[AsyncSession]:
    return get_session_factory()
