from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.auth import create_access_token
from src.core.settings import get_settings
from src.db.base import Base
from src.db.session import get_async_engine
from src.main import app


@pytest.fixture
async def api_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("src.db.session.get_session_factory", lambda eng=None: factory)
    monkeypatch.setattr("src.db.session.get_async_engine", lambda url=None: engine)
    get_async_engine.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await engine.dispose()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    settings = get_settings()
    token = create_access_token(settings.admin_username)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_market_data_download_and_list_cache(
    api_client,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.data import market_cache

    monkeypatch.setattr(market_cache, "CACHE_DIR", tmp_path)
    start = datetime(2026, 4, 1, tzinfo=UTC)
    end = datetime(2026, 7, 1, tzinfo=UTC)

    def _download(**kwargs: object) -> Path:
        path = kwargs["path"]
        assert isinstance(path, Path)
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "timestamp": [start, end],
                "open": [1.0, 1.1],
                "high": [2.0, 2.1],
                "low": [0.5, 0.6],
                "close": [1.5, 1.6],
                "volume": [10.0, 11.0],
            }
        ).to_csv(path, index=False)
        return path

    monkeypatch.setattr(market_cache, "_download_to_csv", _download)

    resp = await api_client.post(
        "/api/v1/market-data/download",
        headers=auth_headers,
        json={
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start_date": "2026-04-01",
            "end_date": "2026-07-01",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["rows"] == 2
    assert body["refreshed"] is True
    assert body["filename"].startswith("binance_BTC-USDT_1h_")

    list_resp = await api_client.get("/api/v1/market-data/cache", headers=auth_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["rows"] == 2

    file_resp = await api_client.get(
        f"/api/v1/market-data/cache/{items[0]['filename']}/file",
        headers=auth_headers,
    )
    assert file_resp.status_code == 200
    assert "timestamp" in file_resp.text

    cached_resp = await api_client.post(
        "/api/v1/market-data/download",
        headers=auth_headers,
        json={
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start_date": "2026-04-01",
            "end_date": "2026-07-01",
            "force": False,
        },
    )
    assert cached_resp.status_code == 200
    assert cached_resp.json()["refreshed"] is False
