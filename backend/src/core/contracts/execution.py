from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class OrderIntent(BaseModel, frozen=True):
    intent_id: str
    decision_id: str
    correlation_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    limit_price: float | None = None
    stop_loss: float
    take_profit: float
    state_snapshot_id: str
    experiment_id: str | None = None
    revision_id: str | None = None


class Order(BaseModel, frozen=True):
    order_id: str
    intent_id: str
    status: Literal[
        "pending",
        "submitted",
        "acknowledged",
        "partially_filled",
        "filled",
        "cancelled",
        "rejected",
    ]
    submitted_at: datetime
    venue: Literal["simulator", "paper", "live"]


class Fill(BaseModel, frozen=True):
    fill_id: str
    order_id: str
    price: float
    quantity: float
    fee: float
    slippage_bps: float
    fill_time: datetime
    is_partial: bool = False


class FillModel(BaseModel, frozen=True):
    model_id: str
    slippage_bps: float = 0.0
    fee_bps: float = 0.0
    fill_at: Literal["close", "next_open", "mid"] = "close"
