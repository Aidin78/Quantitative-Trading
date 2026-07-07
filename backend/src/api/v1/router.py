from fastapi import APIRouter

from src.api.v1 import auth as auth_routes
from src.api.v1 import decisions, engine, providers, replay, signals, validation

api_v1_router = APIRouter()
api_v1_router.include_router(auth_routes.router)
api_v1_router.include_router(decisions.router)
api_v1_router.include_router(engine.router)
api_v1_router.include_router(signals.router)
api_v1_router.include_router(replay.router)
api_v1_router.include_router(validation.router)
api_v1_router.include_router(providers.router)
