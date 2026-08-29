from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.carry import live_state
from src.carry.position_manager import CarryPositionState
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await engine.dispose()


@pytest.mark.asyncio
async def test_portfolio_not_started_when_no_carry_state(api_client, tmp_path, monkeypatch):
    monkeypatch.setattr(live_state, "STATE_PATH", tmp_path / "missing.json")
    resp = await api_client.get("/api/v1/portfolio")
    assert resp.status_code == 200
    body = resp.json()
    assert body["carry"]["status"] == "not_started"
    assert body["blend"]["target_carry_pct"] == 70.0


@pytest.mark.asyncio
async def test_portfolio_reports_carry_sleeve(api_client, tmp_path, monkeypatch):
    monkeypatch.setattr(live_state, "STATE_PATH", tmp_path / "carry.json")
    pos = CarryPositionState(
        spot_qty=0.01, perp_qty=0.01, spot_entry_px=80_000.0, perp_entry_px=80_010.0
    )
    live_state.save_live_state(
        pos,
        cash=333.0,
        spot_baseline=1.0,
        symbol="BTC/USDT",
        mark={
            "at": "2026-08-29T12:00:00+00:00",
            "spot_px": 81_000.0,
            "perp_px": 81_020.0,
            "funding_8h": 0.0001,
            "equity": 1002.5,
            "dry_run": False,
        },
    )
    body = (await api_client.get("/api/v1/portfolio")).json()
    carry = body["carry"]
    assert carry["status"] == "in_market"
    assert carry["equity"] == pytest.approx(1002.5)
    assert carry["net_delta_qty"] == pytest.approx(0.0, abs=1e-9)
    assert carry["funding_apr_pct"] == pytest.approx(0.0001 * 3 * 365 * 100)
    assert body["blend"]["combined_equity"] == pytest.approx(1002.5)
