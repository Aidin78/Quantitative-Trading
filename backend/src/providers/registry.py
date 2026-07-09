from __future__ import annotations

from pathlib import Path

from src.core.contracts.provider import SignalProvider
from src.engine.config import resolve_config_dir
from src.providers.adx_trend_strength import AdxTrendStrengthProvider
from src.providers.base import BaseSignalProvider, ProviderConfig
from src.providers.bollinger_reversion import BollingerReversionProvider
from src.providers.config import load_provider_yaml
from src.providers.ema_crossover import EmaCrossoverProvider
from src.providers.macd_momentum import MacdMomentumProvider
from src.providers.market_structure import MarketStructureProvider
from src.providers.rsi_divergence import RsiDivergenceProvider
from src.providers.supertrend_trend import SuperTrendTrendProvider
from src.providers.volume_order_flow import VolumeOrderFlowProvider

_PROVIDER_CLASSES: dict[str, type[BaseSignalProvider]] = {
    "ema_crossover": EmaCrossoverProvider,
    "rsi_divergence": RsiDivergenceProvider,
    "macd_momentum": MacdMomentumProvider,
    "adx_trend_strength": AdxTrendStrengthProvider,
    "bollinger_reversion": BollingerReversionProvider,
    "supertrend_trend": SuperTrendTrendProvider,
    "volume_order_flow": VolumeOrderFlowProvider,
    "market_structure": MarketStructureProvider,
}


def register_provider(provider_id: str, cls: type[BaseSignalProvider]) -> None:
    _PROVIDER_CLASSES[provider_id] = cls


def discover_provider_configs(config_dir: Path | None = None) -> list[ProviderConfig]:
    base = config_dir or resolve_config_dir()
    providers_dir = base / "providers"
    if not providers_dir.is_dir():
        return []
    configs: list[ProviderConfig] = []
    for path in sorted(providers_dir.glob("*.yaml")):
        configs.append(load_provider_yaml(path))
    return configs


def instantiate_provider(config: ProviderConfig) -> SignalProvider:
    cls = _PROVIDER_CLASSES.get(config.provider_id)
    if cls is None:
        known = ", ".join(sorted(_PROVIDER_CLASSES))
        raise ValueError(f"Unknown provider_id '{config.provider_id}'. Known: {known}")
    return cls(config)


def load_providers(config_dir: Path | None = None) -> list[SignalProvider]:
    return [instantiate_provider(cfg) for cfg in discover_provider_configs(config_dir)]
