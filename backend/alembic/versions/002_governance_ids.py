"""Governance IDs and config revisions."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "002_governance_ids"
down_revision = "001_initial_phase4"
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("event_log", sa.Column("revision_id", sa.String(64), nullable=True))
    op.add_column("event_log", sa.Column("experiment_id", sa.String(64), nullable=True))
    op.add_column("event_log", sa.Column("causation_id", sa.String(64), nullable=True))
    op.create_index("ix_event_log_revision_id", "event_log", ["revision_id"])
    op.create_index("ix_event_log_experiment_id", "event_log", ["experiment_id"])

    op.add_column("decision_records", sa.Column("revision_id", sa.String(64), nullable=True))
    op.add_column("decision_records", sa.Column("experiment_id", sa.String(64), nullable=True))
    op.create_index("ix_decision_records_revision_id", "decision_records", ["revision_id"])
    op.create_index("ix_decision_records_experiment_id", "decision_records", ["experiment_id"])

    op.create_table(
        "config_revisions",
        sa.Column("revision_id", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("engine_config_hash", sa.String(64), nullable=False),
        sa.Column("features_config_hash", sa.String(64), nullable=False),
        sa.Column("providers_config_hash", sa.String(64), nullable=False),
        sa.Column("fill_model_id", sa.String(50), nullable=True),
        sa.Column("risk_limits_hash", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("parent_revision_id", sa.String(64), nullable=True),
        sa.Column("config_bundle", json_type, nullable=False),
    )

    op.create_table(
        "experiments",
        sa.Column("experiment_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=False, server_default=""),
        sa.Column("revision_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("symbols", json_type, nullable=False),
        sa.Column("timeframes", json_type, nullable=False),
        sa.Column("date_range", json_type, nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="system"),
        sa.Column("tags", json_type, nullable=False),
        sa.Column("hypothesis", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_experiments_revision_id", "experiments", ["revision_id"])

    op.create_table(
        "experiment_runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("experiment_id", sa.String(64), nullable=False),
        sa.Column("revision_id", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("metrics_summary", json_type, nullable=True),
    )
    op.create_index("ix_experiment_runs_experiment_id", "experiment_runs", ["experiment_id"])
    op.create_index("ix_experiment_runs_revision_id", "experiment_runs", ["revision_id"])


def downgrade() -> None:
    op.drop_index("ix_experiment_runs_revision_id", table_name="experiment_runs")
    op.drop_index("ix_experiment_runs_experiment_id", table_name="experiment_runs")
    op.drop_table("experiment_runs")
    op.drop_index("ix_experiments_revision_id", table_name="experiments")
    op.drop_table("experiments")
    op.drop_table("config_revisions")
    op.drop_index("ix_decision_records_experiment_id", table_name="decision_records")
    op.drop_index("ix_decision_records_revision_id", table_name="decision_records")
    op.drop_column("decision_records", "experiment_id")
    op.drop_column("decision_records", "revision_id")
    op.drop_index("ix_event_log_experiment_id", table_name="event_log")
    op.drop_index("ix_event_log_revision_id", table_name="event_log")
    op.drop_column("event_log", "causation_id")
    op.drop_column("event_log", "experiment_id")
    op.drop_column("event_log", "revision_id")
