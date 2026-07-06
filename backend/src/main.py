from fastapi import FastAPI

from src.core.settings import get_settings, load_app_yaml_config

app = FastAPI(
    title="Quantitative Trading Platform",
    version="0.1.0",
    description="Decision-centric trading signal platform",
)


@app.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    app_config = load_app_yaml_config()
    return {
        "status": "ok",
        "phase": "3-platform-runtime",
        "environment": settings.environment,
        "app": app_config.app.name,
    }
