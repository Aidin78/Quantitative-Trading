from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PositionState(BaseModel, frozen=True):
    position_id: str
    symbol: str
    side: Literal["LONG", "SHORT"]
    quantity: float
    entry_price: float
    entry_time: datetime
    stop_loss: float | None = None
    take_profit: float | None = None
    unrealized_pnl: float = 0.0
    status: Literal["open", "closed"] = "open"


class RiskLimits(BaseModel, frozen=True):
    max_daily_drawdown_pct: float
    max_open_positions: int
    max_exposure_pct: float
    max_consecutive_losses: int = 5


class PortfolioState(BaseModel, frozen=True):
    portfolio_id: str
    mode: Literal["validation", "live", "paper", "replay"]
    cash: float
    equity: float
    open_positions: tuple[PositionState, ...] = ()
    realized_pnl: float = 0.0
    version: int
    as_of_event_time: datetime
    as_of_processing_time: datetime


class RiskState(BaseModel, frozen=True):
    risk_state_id: str
    portfolio_id: str
    daily_pnl: float = 0.0
    daily_drawdown_pct: float = 0.0
    open_exposure_pct: float = 0.0
    consecutive_losses: int = 0
    limits: RiskLimits
    breached_limits: tuple[str, ...] = ()
    version: int
    as_of_event_time: datetime


class StateSnapshot(BaseModel, frozen=True):
    snapshot_id: str
    portfolio: PortfolioState
    risk: RiskState
    version: int
    created_at: datetime
    correlation_id: str | None = None
