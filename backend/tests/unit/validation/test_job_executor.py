from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.api.services.job_persistence import InMemoryJobPersistence
from src.api.services.validation_service import ValidationJobStore, validation_jobs
from src.validation.harness import ValidationProgressEvent
from src.validation.job_executor import execute_validation_job


@pytest.fixture
def isolated_store() -> ValidationJobStore:
    persistence = InMemoryJobPersistence()
    previous = validation_jobs._persistence
    previous_jobs = dict(validation_jobs._jobs)
    previous_tasks = dict(validation_jobs._tasks)
    validation_jobs._persistence = persistence
    validation_jobs.clear_local()
    yield validation_jobs
    validation_jobs._persistence = previous
    validation_jobs._jobs = previous_jobs
    validation_jobs._tasks = previous_tasks


@pytest.mark.asyncio
async def test_execute_validation_job_honors_cancel_flag(
    isolated_store: ValidationJobStore,
) -> None:
    job = isolated_store.create("job_coop", {"source": "csv", "symbol": "BTC/USDT"})

    async def fake_run(**kwargs):  # noqa: ANN003
        on_progress = kwargs["on_progress"]
        job.status = "running"
        isolated_store.update(job)
        job.cancel_requested = True
        isolated_store.update(job)
        await on_progress(
            ValidationProgressEvent(phase="backtest", message="tick", current=1, total=10)
        )
        raise AssertionError("should have cancelled")

    with patch(
        "src.validation.job_executor.run_validation_job",
        new=AsyncMock(side_effect=fake_run),
    ):
        await execute_validation_job("job_coop", job.config)

    done = isolated_store.get("job_coop")
    assert done is not None
    assert done.status == "cancelled"
