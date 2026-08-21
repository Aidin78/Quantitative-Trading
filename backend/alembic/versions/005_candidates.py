"""Add candidates and candidate_evaluations tables for the promotion lifecycle."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "005_candidates"
down_revision = "004_hypotheses"
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("candidate_id", sa.String(64), primary_key=True),
        sa.Column("experiment_id", sa.String(64), nullable=False),
        sa.Column("hypothesis_id", sa.String(64), nullable=True),
        sa.Column("parent_candidate_id", sa.String(64), nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="candidate"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_candidates_experiment_id", "candidates", ["experiment_id"])
    op.create_index("ix_candidates_hypothesis_id", "candidates", ["hypothesis_id"])
    op.create_index("ix_candidates_parent_candidate_id", "candidates", ["parent_candidate_id"])
    op.create_index("ix_candidates_state", "candidates", ["state"])

    op.create_table(
        "candidate_evaluations",
        sa.Column("evaluation_id", sa.String(64), primary_key=True),
        sa.Column("candidate_id", sa.String(64), nullable=False),
        sa.Column("checks", json_type, nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("decision_reason", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_candidate_evaluations_candidate_id", "candidate_evaluations", ["candidate_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_evaluations_candidate_id", table_name="candidate_evaluations")
    op.drop_table("candidate_evaluations")
    op.drop_index("ix_candidates_state", table_name="candidates")
    op.drop_index("ix_candidates_parent_candidate_id", table_name="candidates")
    op.drop_index("ix_candidates_hypothesis_id", table_name="candidates")
    op.drop_index("ix_candidates_experiment_id", table_name="candidates")
    op.drop_table("candidates")
