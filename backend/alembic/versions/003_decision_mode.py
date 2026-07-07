"""Add mode column to decision_records and backfill from event_log."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "003_decision_mode"
down_revision = "002_governance_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("decision_records", sa.Column("mode", sa.String(16), nullable=True))
    op.create_index("ix_decision_records_mode", "decision_records", ["mode"])
    op.execute(
        """
        UPDATE decision_records AS dr
        SET mode = el.mode
        FROM event_log AS el
        WHERE el.correlation_id = dr.correlation_id
          AND el.mode IS NOT NULL
          AND dr.mode IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_decision_records_mode", table_name="decision_records")
    op.drop_column("decision_records", "mode")
