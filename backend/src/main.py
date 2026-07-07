from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import get_subject_from_token
from src.api.v1.router import api_v1_router
from src.api.websocket.decisions import decision_ws_manager
from src.core.settings import get_settings, load_app_yaml_config
from src.db.session import get_async_engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(get_async_engine())
    yield


app = FastAPI(
    title="Quantitative Trading Platform",
    version="0.1.0",
    description="Decision-centric trading signal platform",
    lifespan=lifespan,
)

settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    app_config = load_app_yaml_config()
    return {
        "status": "ok",
        "phase": "8-governance-foundation",
        "environment": settings.environment,
        "app": app_config.app.name,
        "default_symbol": app_config.default_symbols[0] if app_config.default_symbols else None,
        "default_timeframe": app_config.timeframes[0] if app_config.timeframes else None,
        "symbols": list(app_config.default_symbols),
        "timeframes": list(app_config.timeframes),
    }


@app.websocket("/ws/decisions")
async def ws_decisions(websocket: WebSocket) -> None:
    settings = get_settings()
    if settings.auth_required:
        token = websocket.query_params.get("token")
        if get_subject_from_token(token or "") is None:
            await websocket.close(code=4401)
            return
    await decision_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        decision_ws_manager.disconnect(websocket)
