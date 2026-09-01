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


@pytest.mark.asyncio
async def test_execute_validation_job_applies_strategy_preset(
    isolated_store: ValidationJobStore,
) -> None:
    """Selecting the managed-long-core preset must forward its config bundle and
    force its own timeframe, not the baseline 1h."""
    job = isolated_store.create(
        "job_preset",
        {"source": "csv", "symbol": "BTC/USDT", "timeframe": "1h", "strategy": "managed_long_core"},
    )
    captured: dict = {}

    async def fake_run(**kwargs):  # noqa: ANN003
        captured.update(kwargs)

        class _R:
            outcome_metrics: dict = {}
            engine_metrics: dict = {}
            experiment_run_id = None
            run_id = "run_x"
            revision_id = None
            experiment_id = None

        return _R()

    with patch(
        "src.validation.job_executor.run_validation_job",
        new=AsyncMock(side_effect=fake_run),
    ):
        await execute_validation_job("job_preset", job.config)

    assert captured["timeframe"] == "1d"  # preset wins over the request's 1h
    assert "provider_overrides" in captured
    assert captured["provider_overrides"]["core_long"]["enabled"] is True
    assert captured["execution_config"].long_only is True
