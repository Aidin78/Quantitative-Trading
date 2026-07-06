from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pandas as pd

from src.core.contracts.context import MarketContext
from src.core.contracts.features import FeatureSet, FeatureSetRecord
from src.core.exceptions import DataProviderError
from src.features.config import FeaturesConfig, load_features_config
from src.features.context_deriver import ContextDeriver
from src.features.registry import FeatureRegistry
from src.features.store import FeatureStore

_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


class DefaultFeatureBuilder:
    def __init__(
        self,
        config: FeaturesConfig | None = None,
        config_hash: str | None = None,
        store: FeatureStore | None = None,
    ) -> None:
        if config is None or config_hash is None:
            loaded_config, loaded_hash = load_features_config()
            config = config or loaded_config
            config_hash = config_hash or loaded_hash
        self._config = config
        self._config_hash = config_hash
        self._registry = FeatureRegistry(config)
        self._context_deriver = ContextDeriver(config.context)
        self._store = store

    @property
    def config(self) -> FeaturesConfig:
        return self._config

    @property
    def config_hash(self) -> str:
        return self._config_hash

    def build(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        *,
        processing_time: datetime | None = None,
        persist: bool = True,
    ) -> tuple[FeatureSet, MarketContext]:
        normalized = self._normalize_ohlcv(df)
        event_time = self._event_time_from_df(normalized)
        proc_time = processing_time or datetime.now(UTC)

        indicators: dict[str, float] = {}
        for definition in self._registry.indicators:
            indicators[definition.name] = self._registry.compute_indicator(definition, normalized)

        flags = self._registry.evaluate_flags(indicators)
        close = float(normalized["close"].iloc[-1])

        context = self._context_deriver.derive(
            symbol=symbol,
            timeframe=timeframe,
            close=close,
            indicators=indicators,
            event_time=event_time,
        )

        feature_set = FeatureSet(
            feature_set_id=f"fs_{uuid.uuid4().hex[:12]}",
            symbol=symbol,
            timeframe=timeframe,
            event_time=event_time,
            processing_time=proc_time,
            feature_version=self._config.version,
            config_hash=self._config_hash,
            close=close,
            indicators=indicators,
            flags=flags,
            levels={},
        )

        if self._store is not None and persist:
            record = FeatureSetRecord(
                **feature_set.model_dump(),
                market_context=context,
            )
            self._store.put(record)

        return feature_set, context

    def _normalize_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            raise DataProviderError("OHLCV DataFrame is empty")

        work = df.copy()
        if "timestamp" in work.columns:
            work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True)
            work = work.set_index("timestamp")
        elif not isinstance(work.index, pd.DatetimeIndex):
            raise DataProviderError("OHLCV must have timestamp column or DatetimeIndex")

        if work.index.tz is None:
            work.index = work.index.tz_localize(UTC)
        else:
            work.index = work.index.tz_convert(UTC)

        missing = [col for col in _REQUIRED_COLUMNS if col not in work.columns]
        if missing:
            raise DataProviderError(f"OHLCV missing required columns: {missing}")

        work = work.sort_index()
        return work[list(_REQUIRED_COLUMNS)]

    def _event_time_from_df(self, df: pd.DataFrame) -> datetime:
        ts = df.index[-1]
        if isinstance(ts, pd.Timestamp):
            return ts.to_pydatetime()
        return pd.Timestamp(ts).to_pydatetime()
