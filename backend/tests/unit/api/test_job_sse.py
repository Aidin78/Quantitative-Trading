from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.auth import create_access_token
from src.api.services.job_persistence import InMemoryJobPersistence
from src.api.services.job_progress import (
    format_sse,
    job_progress,
    sse_job_event_stream,
)
from src.api.services.optimization_service import optimization_sweeps
from src.api.services.validation_service import validation_jobs
from src.core.settings import get_settings
from src.main import app


@pytest.fixture(autouse=True)
def _clear_job_stores() -> None:
    persistence = InMemoryJobPersistence()
    optimization_sweeps._persistence = persistence
    validation_jobs._persistence = persistence
    optimization_sweeps.clear_local()
    validation_jobs.clear_local()
    job_progress.clear()
    yield
    optimization_sweeps.clear_local()
    validation_jobs.clear_local()
    job_progress.clear()
    persistence.clear_namespace("optimization")
    persistence.clear_namespace("validation")


@pytest.fixture
def auth_headers() -> dict[str, str]:
    settings = get_settings()
    token = create_access_token(settings.admin_username)
    return {"Authorization": f"Bearer {token}"}


def _parse_sse_events(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        if not block.strip() or block.startswith(":"):
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            events.append((event_name, json.loads("\n".join(data_lines))))
    return events


@pytest.mark.asyncio
async def test_sse_job_event_stream_snapshot_progress_terminal() -> None:
    job_id = "job_direct"
    initial = {"id": job_id, "status": "running", "message": "start"}
    stream = sse_job_event_stream(job_id, initial=initial, heartbeat_seconds=2.0)

    first = await stream.__anext__()
    assert "event: snapshot" in first

    job_progress.publish(
        job_id,
        {"id": job_id, "status": "running", "message": "mid", "progress": {"current": 1}},
    )
    progress = await stream.__anext__()
    assert "event: progress" in progress

    job_progress.publish(job_id, {"id": job_id, "status": "completed", "message": "done"})
    terminal = await stream.__anext__()
    assert "event: terminal" in terminal

    text = "".join([first, progress, terminal])
    events = _parse_sse_events(text)
    names = [name for name, _ in events]
    assert names == ["snapshot", "progress", "terminal"]
    assert events[0][1]["message"] == "start"
    assert events[1][1]["message"] == "mid"
    assert events[2][1]["status"] == "completed"


def test_publish_coalesces_to_latest() -> None:
    queue = job_progress.subscribe("coalesce")
    job_progress.publish("coalesce", {"n": 1})
    job_progress.publish("coalesce", {"n": 2})
    job_progress.publish("coalesce", {"n": 3})
    assert queue.qsize() == 1
    assert queue.get_nowait()["n"] == 3
    job_progress.unsubscribe("coalesce", queue)


def test_format_sse_shape() -> None:
    frame = format_sse("progress", {"id": "x", "status": "running"})
    assert frame.startswith("event: progress\n")
    assert "data: {" in frame
    assert frame.endswith("\n\n")


@pytest.mark.asyncio
async def test_optimization_events_http_terminal_and_auth(
    auth_headers: dict[str, str],
) -> None:
    sweep = optimization_sweeps.create("sweep_done", {})
    sweep.status = "completed"
    sweep.message = "already done"
    optimization_sweeps.update(sweep)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/optimization/sweep_done/events",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        events = _parse_sse_events(response.text)
        names = [name for name, _ in events]
        assert "snapshot" in names
        assert "terminal" in names
        assert events[-1][1]["status"] == "completed"

        missing = await client.get(
            "/api/v1/optimization/missing/events",
            headers=auth_headers,
        )
        assert missing.status_code == 404

        settings = get_settings()
        if settings.auth_required:
            unauth = await client.get("/api/v1/optimization/missing/events")
            assert unauth.status_code in {401, 403}
