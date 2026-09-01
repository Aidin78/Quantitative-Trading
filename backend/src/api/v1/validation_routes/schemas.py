from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ValidationRunRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    csv_path: str | None = None
    source: Literal["exchange", "csv"] = "exchange"
    initial_capital: float = 10000.0
    experiment_id: str | None = None
    revision_id: str | None = None
    max_consecutive_losses: int | None = None
    # named strategy bundle — see src/validation/strategy_presets.py.
    # "baseline" runs the stock demo config; "managed_long_core" runs the one
    # strategy that passed research (its own providers / features / execution).
    strategy: str = "baseline"


class WalkForwardRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    source: Literal["exchange", "csv"] = "exchange"
    initial_capital: float = 10000.0
    windows: int = 3
    train_ratio: float = 0.7


class ValidationRunsBulkDeleteRequest(BaseModel):
    run_ids: list[str]
