from fastapi import APIRouter

from src.api.v1 import (
    analytics,
    config,
    decisions,
    engine,
    experiments,
    live,
    optimization,
    providers,
    replay,
    signals,
    validation,
)
from src.api.v1 import auth as auth_routes

api_v1_router = APIRouter()
api_v1_router.include_router(auth_routes.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(config.router)
api_v1_router.include_router(experiments.router)
api_v1_router.include_router(decisions.router)
api_v1_router.include_router(engine.router)
api_v1_router.include_router(signals.router)
api_v1_router.include_router(replay.router)
api_v1_router.include_router(validation.router)
api_v1_router.include_router(optimization.router)
api_v1_router.include_router(providers.router)
api_v1_router.include_router(live.router)
