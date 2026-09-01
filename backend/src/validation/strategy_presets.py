"""Named strategy bundles for a validation run.

The default config files (`config/engine.yaml`, `config/providers/*.yaml`,
`config/features.yaml`) describe the *baseline* engine — a handful of generic
indicator providers kept around as a demo. The research
(`docs/development/managed-long-core-findings.md`) rejected that set: its gross
edge is smaller than transaction cost. A validation run against it will always
look poor, and that is the honest result for that config.

The one strategy that survived — the managed long-core (trend regime gate +
volatility-targeted sizing) — needs its own bundle: a dedicated feature config
for the regime SMA, `long_only` execution, notional-target sizing, and the
default circuit breakers relaxed so a hold-the-core strategy is not bricked
mid-run by the 5-consecutive-loss breaker.

This module packages that bundle so the dashboard can run it, not just the
`scripts/run_core_long_validation.py` CLI. Keep it in sync with that script.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from src.core.contracts.state import RiskLimits
from src.core.settings import get_settings, resolve_config_dir
from src.engine.config import AggregationConfig, EngineConfig, FilterConfig, RiskConfig
from src.execution.config import ValidationExecutionConfig
from src.features.config import FeaturesConfig, load_features_config_file

# the baseline providers, switched off for a single-strategy run
_BASELINE_PROVIDERS = (
    "ema_crossover",
    "rsi_divergence",
    "macd_momentum",
    "adx_trend_strength",
    "bollinger_reversion",
    "supertrend_trend",
    "volume_order_flow",
    "market_structure",
)


@dataclass(frozen=True)
class StrategyPreset:
    key: str
    label: str
    summary: str
    # recommended run shape — the strategy only makes sense on these
    timeframe: str = "1h"
    default_lookback_days: int = 180
    default_symbols: tuple[str, ...] = ("BTC/USDT",)
    # built lazily (reads config files) when the preset is actually selected
    _run_kwargs_factory: Callable[[], dict] | None = field(default=None, repr=False)

    def run_kwargs(self) -> dict:
        return self._run_kwargs_factory() if self._run_kwargs_factory else {}


def _managed_long_core(*, sma: str = "sma_150", vol_target_atr_pct: float = 2.5) -> dict:
    config_dir = resolve_config_dir(get_settings())
    features: tuple[FeaturesConfig, str] = load_features_config_file(
        config_dir / "features.core_long.yaml"
    )
    engine = EngineConfig(
        aggregation=AggregationConfig(min_agreeing_providers=1, method="weighted_majority"),
        filter=FilterConfig(min_atr_pct=0.0, allowed_sessions=("ASIA", "EUROPE", "US", "OVERLAP")),
        risk=RiskConfig(
            max_daily_drawdown_pct=100.0,
            max_signals_per_day=100,
            min_confidence=0.6,
            min_risk_reward=0.0,
            max_open_positions=1,
            max_exposure_pct=100.0,
            vol_target_atr_pct=vol_target_atr_pct,
            vol_target_cap=1.5,
        ),
    )
    overrides: dict[str, dict] = {p: {"enabled": False} for p in _BASELINE_PROVIDERS}
    overrides["core_long"] = {
        "enabled": True,
        "sma_indicator": sma,
        "confidence": 0.9,
        "min_confidence": 0.6,
        "regime_off_side": "SELL",
        "use_atr_stops": True,
        "sl_atr_mult": 1000.0,  # no stops — exposure only changes on a regime flip
        "tp_atr_mult": 1000.0,
    }
    return {
        "engine_config": engine,
        "provider_overrides": overrides,
        "features_config": features,
        "execution_config": ValidationExecutionConfig(
            max_bars_in_trade=1_000_000,
            risk_pct_per_trade=1.0,
            long_only=True,
            # deploy the whole book into the core position; the vol-target
            # multiplier is what de-risks it (spot, so it can only scale down)
            exposure_pct_per_trade=100.0,
        ),
        "risk_limits": RiskLimits(
            max_daily_drawdown_pct=100.0,
            max_open_positions=1,
            max_exposure_pct=100.0,
            max_consecutive_losses=100_000,
        ),
    }


PRESETS: dict[str, StrategyPreset] = {
    "baseline": StrategyPreset(
        key="baseline",
        label="Baseline engine (demo)",
        summary=(
            "The stock config: generic indicator providers with no validated "
            "edge. Use it to exercise the engine, not to judge strategy P&L."
        ),
        timeframe="1h",
        default_lookback_days=180,
    ),
    "managed_long_core": StrategyPreset(
        key="managed_long_core",
        label="Managed long-core (deployable)",
        summary=(
            "Trend regime gate (close above SMA-150) plus volatility-targeted "
            "sizing. The one strategy that passed research. Trades about 4x a "
            "year, so it needs a multi-year window: the edge is the deep bear "
            "markets it sits out."
        ),
        timeframe="1d",
        default_lookback_days=365 * 7,
        default_symbols=("BTC/USDT", "ETH/USDT"),
        _run_kwargs_factory=_managed_long_core,
    ),
}


def resolve_preset(key: str | None) -> StrategyPreset:
    return PRESETS.get(key or "baseline", PRESETS["baseline"])
