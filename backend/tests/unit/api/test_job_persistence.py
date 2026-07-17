from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.api.services.job_persistence import (
    InMemoryJobPersistence,
    RedisJobPersistence,
    create_job_persistence,
)
from src.api.services.optimization_service import (
    ACTIVE_LIVE_TRIAL_CAP,
    OptimizationSweep,
    OptimizationSweepStore,
    sweep_progress_response,
    sweep_response,
)
from src.api.services.validation_service import ValidationJobStore, job_response
from src.core.settings import get_settings


def test_create_job_persistence_falls_back_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://invalid:59999/0")
    get_settings.cache_clear()
    persistence = create_job_persistence(prefer_redis=True)
    assert isinstance(persistence, InMemoryJobPersistence)


def test_in_memory_persistence_roundtrip() -> None:
    persistence = InMemoryJobPersistence()
    persistence.save("optimization", "sweep_1", {"id": "sweep_1", "status": "running"})
    assert persistence.has_active("optimization") is True
    loaded = persistence.load("optimization", "sweep_1")
    assert loaded is not None
    assert loaded["status"] == "running"
    persistence.save("optimization", "sweep_1", {"id": "sweep_1", "status": "completed"})
    assert persistence.has_active("optimization") is False


def test_redis_persistence_roundtrip() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    client = fakeredis.FakeRedis(decode_responses=True)
    persistence = RedisJobPersistence(client)
    persistence.save(
        "validation",
        "job_1",
        {"id": "job_1", "status": "running", "config": {}},
    )
    assert persistence.has_active("validation") is True
    assert persistence.load("validation", "job_1")["status"] == "running"
    persistence.save(
        "validation",
        "job_1",
        {"id": "job_1", "status": "completed", "config": {}},
    )
    assert persistence.has_active("validation") is False


def test_optimization_store_survives_local_clear() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    persistence = RedisJobPersistence(fakeredis.FakeRedis(decode_responses=True))
    store = OptimizationSweepStore(persistence=persistence)
    sweep = store.create("sweep_restart", {"symbol": "BTC/USDT"})
    sweep.status = "completed"
    sweep.result_snapshot = {
        "sweep_id": "sweep_restart",
        "symbol": "BTC/USDT",
        "best_valid": True,
        "best": {"params": {"min_confidence": 0.7}, "trial_id": "t1"},
    }
    store.update(sweep)

    store.clear_local()
    restored = store.get("sweep_restart")
    assert restored is not None
    assert restored.status == "completed"
    assert restored.result is None
    assert restored.result_snapshot is not None
    payload = sweep_response(restored)
    assert payload["best"]["params"]["min_confidence"] == 0.7


def test_validation_store_marks_orphaned_running_as_failed() -> None:
    persistence = InMemoryJobPersistence()
    store = ValidationJobStore(persistence=persistence)
    job = store.create("job_orphan", {"symbol": "ETH/USDT"})
    job.status = "running"
    job.progress_current = 10
    job.progress_total = 100
    store.update(job)

    store.clear_local()
    restored = store.get("job_orphan")
    assert restored is not None
    assert restored.status == "failed"
    assert "restart" in (restored.error or "").lower()
    payload = job_response(restored)
    assert payload["status"] == "failed"


def test_redis_enqueue_dequeue_roundtrip() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    persistence = RedisJobPersistence(fakeredis.FakeRedis(decode_responses=True))
    persistence.enqueue("validation", "job_q1")
    assert persistence.blocking_dequeue("validation", timeout=1) == "job_q1"
    assert persistence.blocking_dequeue("validation", timeout=1) is None


def test_redis_validation_preserves_pending_for_worker() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    persistence = RedisJobPersistence(fakeredis.FakeRedis(decode_responses=True))
    store = ValidationJobStore(persistence=persistence)
    assert store.uses_job_queue() is True
    store.create("job_queued", {"symbol": "BTC/USDT", "source": "csv"})
    store.clear_local()
    restored = store.get("job_queued")
    assert restored is not None
    assert restored.status == "pending"
    assert store.has_active() is True


def test_cancel_without_local_task_persists_flag() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    persistence = RedisJobPersistence(fakeredis.FakeRedis(decode_responses=True))
    store = ValidationJobStore(persistence=persistence)
    job = store.create("job_cancel_flag", {"source": "csv"})
    job.status = "running"
    store.update(job)
    store.clear_local()

    cancelled = store.request_cancel("job_cancel_flag")
    assert cancelled is not None
    assert cancelled.cancel_requested is True
    store.clear_local()
    reloaded = store.get("job_cancel_flag")
    assert reloaded is not None
    assert reloaded.cancel_requested is True
    assert reloaded.status == "running"


def test_has_active_sees_persisted_running_job() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    client = fakeredis.FakeRedis(decode_responses=True)
    persistence = RedisJobPersistence(client)
    writer = OptimizationSweepStore(persistence=persistence)
    reader = OptimizationSweepStore(persistence=persistence)

    sweep = writer.create("sweep_active", {})
    sweep.status = "running"
    writer.update(sweep)
    writer.clear_local()

    assert reader.has_active() is True
    # Queue-backed stores preserve active status for the durable worker.
    restored = reader.get("sweep_active")
    assert restored is not None
    assert restored.status == "running"
    assert reader.has_active() is True


def test_redis_optimization_preserves_pending_for_worker() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    persistence = RedisJobPersistence(fakeredis.FakeRedis(decode_responses=True))
    store = OptimizationSweepStore(persistence=persistence)
    assert store.uses_job_queue() is True
    store.create("sweep_queued", {"max_trials": 1, "source": "csv"})
    store.clear_local()
    restored = store.get("sweep_queued")
    assert restored is not None
    assert restored.status == "pending"
    assert store.has_active() is True


def test_optimization_cancel_without_local_task_persists_flag() -> None:
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed")

    persistence = RedisJobPersistence(fakeredis.FakeRedis(decode_responses=True))
    store = OptimizationSweepStore(persistence=persistence)
    sweep = store.create("sweep_cancel_flag", {"source": "csv"})
    sweep.status = "running"
    store.update(sweep)
    store.clear_local()

    cancelled = store.request_cancel("sweep_cancel_flag")
    assert cancelled is not None
    assert cancelled.cancel_requested is True
    store.clear_local()
    reloaded = store.get("sweep_cancel_flag")
    assert reloaded is not None
    assert reloaded.cancel_requested is True
    assert reloaded.status == "running"


def test_sweep_created_at_roundtrip_iso() -> None:
    persistence = InMemoryJobPersistence()
    store = OptimizationSweepStore(persistence=persistence)
    sweep = OptimizationSweep(
        id="sweep_ts",
        status="pending",
        config={},
        created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    store.update(sweep)
    store.clear_local()
    restored = store.get("sweep_ts")
    assert restored is not None
    assert restored.created_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_active_serialize_caps_live_trial_snapshots() -> None:
    persistence = InMemoryJobPersistence()
    store = OptimizationSweepStore(persistence=persistence)
    sweep = store.create("sweep_cap", {"source": "csv"})
    sweep.status = "running"
    sweep.live_trial_snapshots = [
        {"trial_id": f"t{i}", "params": {}} for i in range(ACTIVE_LIVE_TRIAL_CAP + 15)
    ]
    store.update(sweep)
    record = persistence.load("optimization", "sweep_cap")
    assert record is not None
    assert len(record["live_trial_snapshots"]) == ACTIVE_LIVE_TRIAL_CAP
    assert record["live_trial_snapshots"][0]["trial_id"] == "t15"
    assert record["live_trial_snapshots"][-1]["trial_id"] == f"t{ACTIVE_LIVE_TRIAL_CAP + 14}"


def test_completed_serialize_keeps_full_live_trials() -> None:
    persistence = InMemoryJobPersistence()
    store = OptimizationSweepStore(persistence=persistence)
    sweep = store.create("sweep_full", {"source": "csv"})
    sweep.status = "completed"
    sweep.live_trial_snapshots = [
        {"trial_id": f"t{i}", "params": {}} for i in range(ACTIVE_LIVE_TRIAL_CAP + 5)
    ]
    store.update(sweep)
    record = persistence.load("optimization", "sweep_full")
    assert record is not None
    assert len(record["live_trial_snapshots"]) == ACTIVE_LIVE_TRIAL_CAP + 5


def test_progress_response_omits_trials() -> None:
    sweep = OptimizationSweep(
        id="sweep_slim",
        status="running",
        config={"source": "csv"},
        phase="train",
        message="Training…",
        progress_current=3,
        progress_total=10,
        live_trial_snapshots=[{"trial_id": "t1", "params": {}}],
    )
    slim = sweep_progress_response(sweep)
    assert "trials" not in slim
    assert slim["phase"] == "train"
    assert slim["progress"]["current"] == 3
    full = sweep_response(sweep)
    assert full["trials"][0]["trial_id"] == "t1"
