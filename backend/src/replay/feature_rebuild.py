from __future__ import annotations

from typing import Any

from src.core.contracts.event import EventEnvelope
from src.data.csv_provider import CsvDataProvider
from src.features.builder import DefaultFeatureBuilder
from src.features.config import FeaturesConfig
from src.validation.lookback import compute_min_lookback_bars


def _resolve_csv_path(csv_path: str | None):
    from pathlib import Path

    if csv_path:
        return Path(csv_path)
    backend_root = Path(__file__).resolve().parents[2]
    candidates = [
        backend_root / "tests" / "fixtures" / "sample_btc_1h.csv",
        backend_root / "tests" / "fixtures" / "ohlcv_btc_1h.csv",
        Path("/app/data/ohlcv_btc_1h.csv"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def rebuild_indicators(
    feature_event: EventEnvelope,
    *,
    csv_path: str | None = None,
    features_config: FeaturesConfig | None = None,
    config_hash: str | None = None,
) -> dict[str, Any] | None:
    """Rebuild indicators/flags from OHLCV at event_time.

    Returns ``{"indicators": ..., "flags": ...}`` or ``None`` if OHLCV/config
    rebuild is unavailable. Uses ``features_config`` / ``config_hash`` when
    provided; otherwise loads the current disk features config.
    """
    path = _resolve_csv_path(csv_path)
    if path is None:
        return None
    try:
        provider = CsvDataProvider(
            path,
            symbol=feature_event.symbol,
            timeframe=feature_event.timeframe,
        )
        limit = max(compute_min_lookback_bars() + 10, 200)
        df = provider.get_latest(
            feature_event.symbol,
            feature_event.timeframe,
            limit=limit,
            end=feature_event.event_time,
        )
        if features_config is not None and config_hash is not None:
            builder = DefaultFeatureBuilder(config=features_config, config_hash=config_hash)
        else:
            builder = DefaultFeatureBuilder()
        feature_set, _ = builder.build(
            df,
            feature_event.symbol,
            feature_event.timeframe,
            processing_time=feature_event.processing_time,
            persist=False,
        )
        return {
            "indicators": feature_set.indicators,
            "flags": feature_set.flags,
        }
    except Exception:
        return None
