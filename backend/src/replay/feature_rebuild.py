from __future__ import annotations

from src.core.contracts.event import EventEnvelope
from src.data.csv_provider import CsvDataProvider
from src.features.builder import DefaultFeatureBuilder
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
) -> dict[str, float] | None:
    """Rebuild indicators from OHLCV at event_time using current features config."""
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
        builder = DefaultFeatureBuilder()
        feature_set, _ = builder.build(
            df,
            feature_event.symbol,
            feature_event.timeframe,
            processing_time=feature_event.processing_time,
            persist=False,
        )
        return feature_set.indicators
    except Exception:
        return None
