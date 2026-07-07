"""Initial Phase 4 schema."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "001_initial_phase4"
down_revision = None
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "event_log",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("event_family", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("payload", json_type, nullable=False),
    )
    op.create_index("ix_event_log_correlation_id", "event_log", ["correlation_id"])
    op.create_index("ix_event_log_event_time", "event_log", ["event_time"])

    op.create_table(
        "decision_records",
        sa.Column("decision_id", sa.String(64), primary_key=True),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("state_snapshot_id", sa.String(64), nullable=False),
        sa.Column("decision_log", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "backtest_runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("config", json_type, nullable=False),
        sa.Column("metrics", json_type, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "simulated_trades",
        sa.Column("trade_id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("position_id", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("pnl", sa.Float(), nullable=False),
        sa.Column("exit_reason", sa.String(32), nullable=False),
        sa.Column("payload", json_type, nullable=False),
    )

    op.create_table(
        "feature_sets",
        sa.Column("feature_set_id", sa.String(64), primary_key=True),
        sa.Column("feature_version", sa.String(32), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "state_snapshots",
        sa.Column("snapshot_id", sa.String(64), primary_key=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("portfolio", json_type, nullable=False),
        sa.Column("risk", json_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(64), primary_key=True),
        sa.Column("intent_id", sa.String(64), nullable=False),
        sa.Column("decision_id", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("venue", sa.String(20), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_orders_correlation_id", "orders", ["correlation_id"])

    op.create_table(
        "fills",
        sa.Column("fill_id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("slippage_bps", sa.Float(), nullable=False),
        sa.Column("fill_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fill_model_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fills_order_id", "fills", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_fills_order_id", table_name="fills")
    op.drop_table("fills")
    op.drop_index("ix_orders_correlation_id", table_name="orders")
    op.drop_table("orders")
    op.drop_table("state_snapshots")
    op.drop_table("feature_sets")
    op.drop_table("simulated_trades")
    op.drop_table("backtest_runs")
    op.drop_table("decision_records")
    op.drop_index("ix_event_log_event_time", table_name="event_log")
    op.drop_index("ix_event_log_correlation_id", table_name="event_log")
    op.drop_table("event_log")
