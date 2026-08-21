from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConfigRevision(BaseModel, frozen=True):
    revision_id: str
    created_at: datetime
    engine_config_hash: str
    features_config_hash: str
    providers_config_hash: str
    fill_model_id: str | None = None
    risk_limits_hash: str
    label: str
    parent_revision_id: str | None = None
    config_bundle: dict[str, Any] = Field(default_factory=dict)


class Experiment(BaseModel, frozen=True):
    experiment_id: str
    name: str
    description: str = ""
    revision_id: str
    status: Literal["draft", "running", "completed", "archived"]
    mode: Literal["validation", "live", "paper", "replay"]
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    date_range: tuple[datetime, datetime] | None = None
    created_by: str = "system"
    tags: tuple[str, ...] = ()
    hypothesis: str | None = None


class ExperimentRun(BaseModel, frozen=True):
    run_id: str
    experiment_id: str
    revision_id: str
    started_at: datetime
    completed_at: datetime | None = None
    status: Literal["running", "completed", "failed", "cancelled"]
    metrics_summary: dict[str, float] | None = None


class Hypothesis(BaseModel, frozen=True):
    """Structured Observation -> Hypothesis -> Expected Effect -> Proposed
    Change record, distinct from Experiment.hypothesis (free text). Links back
    to the ExperimentRun whose result motivated it, and forward to whichever
    Experiment was created to test it, so "have we tried this" is a query
    instead of a memory.
    """

    hypothesis_id: str
    observation: str
    statement: str
    expected_effect: str
    proposed_change: str
    source_experiment_run_id: str | None = None
    tested_by_experiment_id: str | None = None
    status: Literal["open", "tested", "confirmed", "refuted"] = "open"
    created_by: str = "system"
    created_at: datetime
