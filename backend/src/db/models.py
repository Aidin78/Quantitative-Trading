from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.db.base import Base

JsonType = JSON().with_variant(JSONB, "postgresql")


class EventLogRow(Base):
    __tablename__ = "event_log"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_family: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    processing_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(16))
    mode: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JsonType)


class DecisionRecordRow(Base):
    __tablename__ = "decision_records"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    correlation_id: Mapped[str] = mapped_column(String(128), index=True)
    result: Mapped[str] = mapped_column(String(16))
    state_snapshot_id: Mapped[str] = mapped_column(String(64))
    decision_log: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BacktestRunRow(Base):
    __tablename__ = "backtest_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(16))
    config: Mapped[dict] = mapped_column(JsonType)
    metrics: Mapped[dict] = mapped_column(JsonType)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SimulatedTradeRow(Base):
    __tablename__ = "simulated_trades"

    trade_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    position_id: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    pnl: Mapped[float] = mapped_column(Float)
    exit_reason: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JsonType)


class FeatureSetRow(Base):
    __tablename__ = "feature_sets"

    feature_set_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feature_version: Mapped[str] = mapped_column(String(32))
    config_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StateSnapshotRow(Base):
    __tablename__ = "state_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    portfolio: Mapped[dict] = mapped_column(JsonType)
    risk: Mapped[dict] = mapped_column(JsonType)
    version: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrderRow(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent_id: Mapped[str] = mapped_column(String(64), index=True)
    decision_id: Mapped[str] = mapped_column(String(64), index=True)
    correlation_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(30))
    venue: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FillRow(Base):
    __tablename__ = "fills"

    fill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float)
    slippage_bps: Mapped[float] = mapped_column(Float)
    fill_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fill_model_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
