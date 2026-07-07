from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.contracts.governance import Experiment, ExperimentRun
from src.core.settings import load_app_yaml_config
from src.db.models import BacktestRunRow, ExperimentRow, ExperimentRunRow


def _row_to_experiment(row: ExperimentRow) -> Experiment:
    date_range = None
    if row.date_range:
        date_range = (
            datetime.fromisoformat(row.date_range["start"]),
            datetime.fromisoformat(row.date_range["end"]),
        )
    return Experiment(
        experiment_id=row.experiment_id,
        name=row.name,
        description=row.description,
        revision_id=row.revision_id,
        status=row.status,  # type: ignore[arg-type]
        mode=row.mode,  # type: ignore[arg-type]
        symbols=tuple(row.symbols),
        timeframes=tuple(row.timeframes),
        date_range=date_range,
        created_by=row.created_by,
        tags=tuple(row.tags or []),
        hypothesis=row.hypothesis,
    )


async def create_experiment(
    session: AsyncSession,
    *,
    revision_id: str,
    name: str,
    mode: str = "validation",
    symbols: tuple[str, ...] | None = None,
    timeframes: tuple[str, ...] | None = None,
    description: str = "",
    hypothesis: str | None = None,
) -> Experiment:
    app = load_app_yaml_config()
    exp_id = f"exp_{uuid.uuid4().hex[:12]}"
    syms = symbols or app.default_symbols
    tfs = timeframes or app.timeframes
    row = ExperimentRow(
        experiment_id=exp_id,
        name=name,
        description=description,
        revision_id=revision_id,
        status="running",
        mode=mode,
        symbols=list(syms),
        timeframes=list(tfs),
        date_range=None,
        created_by="system",
        tags=[],
        hypothesis=hypothesis,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return _row_to_experiment(row)


async def get_experiment(session: AsyncSession, experiment_id: str) -> Experiment | None:
    row = await session.get(ExperimentRow, experiment_id)
    if row is None:
        return None
    return _row_to_experiment(row)


async def list_experiments(session: AsyncSession, *, limit: int = 50) -> list[Experiment]:
    stmt = select(ExperimentRow).order_by(ExperimentRow.created_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_experiment(row) for row in rows]


async def create_experiment_run(
    session: AsyncSession,
    *,
    experiment_id: str,
    revision_id: str,
    run_id: str | None = None,
) -> ExperimentRun:
    run = ExperimentRunRow(
        run_id=run_id or f"erun_{uuid.uuid4().hex[:12]}",
        experiment_id=experiment_id,
        revision_id=revision_id,
        started_at=datetime.now(UTC),
        completed_at=None,
        status="running",
        metrics_summary=None,
    )
    session.add(run)
    await session.flush()
    return ExperimentRun(
        run_id=run.run_id,
        experiment_id=run.experiment_id,
        revision_id=run.revision_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,  # type: ignore[arg-type]
        metrics_summary=run.metrics_summary,
    )


async def complete_experiment_run(
    session: AsyncSession,
    run_id: str,
    *,
    status: str,
    metrics_summary: dict[str, float] | None = None,
) -> None:
    row = await session.get(ExperimentRunRow, run_id)
    if row is None:
        return
    row.status = status
    row.completed_at = datetime.now(UTC)
    row.metrics_summary = metrics_summary
    exp = await session.get(ExperimentRow, row.experiment_id)
    if exp is not None:
        exp.status = "completed" if status == "completed" else exp.status


async def has_successful_validation(session: AsyncSession, revision_id: str) -> bool:
    app = load_app_yaml_config()
    min_trades = app.validation.min_trades
    stmt = select(BacktestRunRow)
    rows = (await session.execute(stmt)).scalars().all()
    for row in rows:
        cfg = row.config or {}
        if cfg.get("revision_id") != revision_id:
            continue
        outcome = (row.metrics or {}).get("outcome", {})
        total_trades = int(outcome.get("total_trades", 0))
        if row.completed_at and total_trades >= min_trades:
            return True
    stmt2 = select(ExperimentRunRow).where(ExperimentRunRow.revision_id == revision_id)
    runs = (await session.execute(stmt2)).scalars().all()
    for run in runs:
        if run.status != "completed":
            continue
        summary = run.metrics_summary or {}
        if int(summary.get("total_trades", 0)) >= min_trades:
            return True
    return False
