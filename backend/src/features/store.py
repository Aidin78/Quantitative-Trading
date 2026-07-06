from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.core.contracts.features import FeatureSetRecord


class FeatureStore(Protocol):
    def put(self, record: FeatureSetRecord) -> None: ...

    def get(self, feature_set_id: str) -> FeatureSetRecord: ...

    def get_at(
        self,
        symbol: str,
        timeframe: str,
        event_time: datetime,
        feature_version: str,
    ) -> FeatureSetRecord | None: ...


class InMemoryFeatureStore:
    def __init__(self) -> None:
        self._by_id: dict[str, FeatureSetRecord] = {}
        self._by_lookup: dict[tuple[str, str, datetime, str], str] = {}

    def put(self, record: FeatureSetRecord) -> None:
        self._by_id[record.feature_set_id] = record
        key = (record.symbol, record.timeframe, record.event_time, record.feature_version)
        self._by_lookup[key] = record.feature_set_id

    def get(self, feature_set_id: str) -> FeatureSetRecord:
        if feature_set_id not in self._by_id:
            raise KeyError(f"FeatureSetRecord not found: {feature_set_id}")
        return self._by_id[feature_set_id]

    def get_at(
        self,
        symbol: str,
        timeframe: str,
        event_time: datetime,
        feature_version: str,
    ) -> FeatureSetRecord | None:
        feature_set_id = self._by_lookup.get((symbol, timeframe, event_time, feature_version))
        if feature_set_id is None:
            return None
        return self._by_id.get(feature_set_id)

    def clear(self) -> None:
        self._by_id.clear()
        self._by_lookup.clear()

    @property
    def size(self) -> int:
        return len(self._by_id)
