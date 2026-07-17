from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.api.services.job_persistence import InMemoryJobPersistence
from src.api.services.optimization_service import OptimizationSweepStore, optimization_sweeps
from src.validation.optimization_job_executor import execute_optimization_sweep
from src.validation.optimizer import ProgressEvent


@pytest.fixture
def isolated_sweep_store() -> OptimizationSweepStore:
    persistence = InMemoryJobPersistence()
    previous = optimization_sweeps._persistence
    previous_sweeps = dict(optimization_sweeps._sweeps)
    previous_tasks = dict(optimization_sweeps._tasks)
    optimization_sweeps._persistence = persistence
    optimization_sweeps.clear_local()
    yield optimization_sweeps
    optimization_sweeps._persistence = previous
    optimization_sweeps._sweeps = previous_sweeps
    optimization_sweeps._tasks = previous_tasks


@pytest.mark.asyncio
async def test_execute_optimization_sweep_honors_cancel_flag(
    isolated_sweep_store: OptimizationSweepStore,
) -> None:
    sweep = isolated_sweep_store.create(
        "sweep_coop",
        {"source": "csv", "symbol": "BTC/USDT", "max_trials": 1},
    )

    async def fake_run(**kwargs):  # noqa: ANN003
        on_progress = kwargs["on_progress"]
        sweep.status = "running"
        isolated_sweep_store.update(sweep)
        sweep.cancel_requested = True
        isolated_sweep_store.update(sweep)
        await on_progress(
            ProgressEvent(
                phase="train",
                stage="start",
                current=0,
                total=1,
                train_count=1,
                test_count=0,
            )
        )
        raise AssertionError("should have cancelled")

    with patch(
        "src.validation.optimization_job_executor.run_optimization",
        new=AsyncMock(side_effect=fake_run),
    ):
        await execute_optimization_sweep("sweep_coop", sweep.config)

    done = isolated_sweep_store.get("sweep_coop")
    assert done is not None
    assert done.status == "cancelled"
