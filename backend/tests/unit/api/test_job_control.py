from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.auth import create_access_token
from src.api.services.optimization_service import optimization_sweeps
from src.api.services.validation_service import validation_jobs
from src.core.settings import get_settings
from src.main import app


@pytest.fixture(autouse=True)
def _clear_job_stores() -> None:
    optimization_sweeps._sweeps.clear()
    optimization_sweeps._tasks.clear()
    validation_jobs._jobs.clear()
    validation_jobs._tasks.clear()
    yield
    optimization_sweeps._sweeps.clear()
    optimization_sweeps._tasks.clear()
    validation_jobs._jobs.clear()
    validation_jobs._tasks.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    settings = get_settings()
    token = create_access_token(settings.admin_username)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_optimization_rejects_second_run_with_429(auth_headers: dict[str, str]) -> None:
    async def slow_execute(sweep_id: str, body) -> None:  # noqa: ANN001
        sweep = optimization_sweeps.get(sweep_id)
        assert sweep is not None
        sweep.status = "running"
        optimization_sweeps.update(sweep)
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            sweep.status = "cancelled"
            optimization_sweeps.update(sweep)
            raise
        finally:
            optimization_sweeps.clear_task(sweep_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "src.api.v1.optimization._execute_sweep",
            new=slow_execute,
        ):
            first = await client.post(
                "/api/v1/optimization/run",
                json={"max_trials": 1, "source": "csv"},
                headers=auth_headers,
            )
            assert first.status_code == 200
            second = await client.post(
                "/api/v1/optimization/run",
                json={"max_trials": 1, "source": "csv"},
                headers=auth_headers,
            )
            assert second.status_code == 429
            cancel = await client.post(
                f"/api/v1/optimization/{first.json()['id']}/cancel",
                headers=auth_headers,
            )
            assert cancel.status_code == 200
            await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_optimization_cancel_sets_cancelled_status(
    auth_headers: dict[str, str],
) -> None:
    started = asyncio.Event()

    async def slow_execute(sweep_id: str, body) -> None:  # noqa: ANN001
        from src.api.services.optimization_service import JobCancelled

        sweep = optimization_sweeps.get(sweep_id)
        assert sweep is not None
        sweep.status = "running"
        optimization_sweeps.update(sweep)
        started.set()
        try:
            while True:
                current = optimization_sweeps.get(sweep_id)
                if current is not None and current.cancel_requested:
                    raise JobCancelled("cancelled")
                await asyncio.sleep(0.01)
        except (asyncio.CancelledError, JobCancelled):
            sweep.status = "cancelled"
            sweep.message = "Optimization cancelled."
            optimization_sweeps.update(sweep)
        finally:
            optimization_sweeps.clear_task(sweep_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "src.api.v1.optimization._execute_sweep",
            new=slow_execute,
        ):
            started_resp = await client.post(
                "/api/v1/optimization/run",
                json={"max_trials": 1, "source": "csv"},
                headers=auth_headers,
            )
            sweep_id = started_resp.json()["id"]
            await started.wait()
            cancel = await client.post(
                f"/api/v1/optimization/{sweep_id}/cancel",
                headers=auth_headers,
            )
            assert cancel.status_code == 200
            await asyncio.sleep(0.05)
            status = await client.get(
                f"/api/v1/optimization/{sweep_id}",
                headers=auth_headers,
            )
            assert status.status_code == 200
            assert status.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_validation_rejects_second_run_with_429(auth_headers: dict[str, str]) -> None:
    async def slow_execute(job_id: str, body) -> None:  # noqa: ANN001
        job = validation_jobs.get(job_id)
        assert job is not None
        job.status = "running"
        validation_jobs.update(job)
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            job.status = "cancelled"
            validation_jobs.update(job)
            raise
        finally:
            validation_jobs.clear_task(job_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "src.api.v1.validation._execute_job",
            new=slow_execute,
        ):
            first = await client.post(
                "/api/v1/validation/run",
                json={"source": "csv"},
                headers=auth_headers,
            )
            assert first.status_code == 200
            second = await client.post(
                "/api/v1/validation/run",
                json={"source": "csv"},
                headers=auth_headers,
            )
            assert second.status_code == 429
            await client.post(
                f"/api/v1/validation/{first.json()['id']}/cancel",
                headers=auth_headers,
            )
            await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_validation_cancel_sets_cancelled_status(auth_headers: dict[str, str]) -> None:
    started = asyncio.Event()

    async def slow_execute(job_id: str, body) -> None:  # noqa: ANN001
        from src.api.services.validation_service import JobCancelled

        job = validation_jobs.get(job_id)
        assert job is not None
        job.status = "running"
        validation_jobs.update(job)
        started.set()
        try:
            while True:
                current = validation_jobs.get(job_id)
                if current is not None and current.cancel_requested:
                    raise JobCancelled("cancelled")
                await asyncio.sleep(0.01)
        except (asyncio.CancelledError, JobCancelled):
            job.status = "cancelled"
            job.message = "Validation cancelled."
            validation_jobs.update(job)
        finally:
            validation_jobs.clear_task(job_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "src.api.v1.validation._execute_job",
            new=slow_execute,
        ):
            started_resp = await client.post(
                "/api/v1/validation/run",
                json={"source": "csv"},
                headers=auth_headers,
            )
            job_id = started_resp.json()["id"]
            await started.wait()
            cancel = await client.post(
                f"/api/v1/validation/{job_id}/cancel",
                headers=auth_headers,
            )
            assert cancel.status_code == 200
            await asyncio.sleep(0.05)
            status = await client.get(
                f"/api/v1/validation/{job_id}",
                headers=auth_headers,
            )
            assert status.status_code == 200
            assert status.json()["status"] == "cancelled"
