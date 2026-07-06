from fastapi import FastAPI

app = FastAPI(
    title="Quantitative Trading Platform",
    version="0.1.0",
    description="Decision-centric trading signal platform",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "phase": "0-contracts"}
