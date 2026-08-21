"""Add hypotheses table for structured research hypotheses."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "004_hypotheses"
down_revision = "003_decision_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hypotheses",
        sa.Column("hypothesis_id", sa.String(64), primary_key=True),
        sa.Column("observation", sa.String(2000), nullable=False),
        sa.Column("statement", sa.String(2000), nullable=False),
        sa.Column("expected_effect", sa.String(2000), nullable=False),
        sa.Column("proposed_change", sa.String(2000), nullable=False),
        sa.Column("source_experiment_run_id", sa.String(64), nullable=True),
        sa.Column("tested_by_experiment_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_hypotheses_source_experiment_run_id", "hypotheses", ["source_experiment_run_id"]
    )
    op.create_index(
        "ix_hypotheses_tested_by_experiment_id", "hypotheses", ["tested_by_experiment_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_hypotheses_tested_by_experiment_id", table_name="hypotheses")
    op.drop_index("ix_hypotheses_source_experiment_run_id", table_name="hypotheses")
    op.drop_table("hypotheses")
