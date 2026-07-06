from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AggregatorSuccess:
    side: Literal["BUY", "SELL"]
    confidence: float
    weights: dict[str, float]
    dissent: tuple[str, ...]


@dataclass(frozen=True)
class AggregatorFailure:
    reason: str


AggregatorOutcome = AggregatorSuccess | AggregatorFailure
