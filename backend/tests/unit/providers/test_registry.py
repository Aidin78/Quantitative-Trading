from __future__ import annotations

from pathlib import Path

import pytest

from src.engine.config import resolve_config_dir
from src.providers.base import BaseSignalProvider, ProviderConfig
from src.providers.registry import (
    discover_provider_configs,
    instantiate_provider,
    load_providers,
    register_provider,
)


def test_discover_provider_configs_from_repo() -> None:
    configs = discover_provider_configs(resolve_config_dir())
    ids = {c.provider_id for c in configs}
    assert "ema_crossover" in ids
    assert "rsi_divergence" in ids


def test_load_providers_returns_instances() -> None:
    providers = load_providers(resolve_config_dir())
    assert len(providers) >= 2
    assert {p.provider_id for p in providers} >= {"ema_crossover", "rsi_divergence"}


def test_unknown_provider_id_raises() -> None:
    with pytest.raises(ValueError, match="Unknown provider_id"):
        instantiate_provider(ProviderConfig(provider_id="unknown_provider"))


def test_enabled_false_config_still_instantiates() -> None:
    provider = instantiate_provider(ProviderConfig(provider_id="ema_crossover", enabled=False))
    assert provider.enabled is False


class _DummyProvider(BaseSignalProvider):
    def analyze(self, features, context):
        raise NotImplementedError


def test_register_third_provider(tmp_path: Path) -> None:
    register_provider("dummy_test", _DummyProvider)
    yaml_path = tmp_path / "providers" / "dummy_test.yaml"
    yaml_path.parent.mkdir(parents=True)
    yaml_path.write_text(
        "provider_id: dummy_test\nenabled: true\nweight: 0.5\nparams: {}\n",
        encoding="utf-8",
    )
    providers = load_providers(tmp_path)
    dummy = next(p for p in providers if p.provider_id == "dummy_test")
    assert dummy.weight == 0.5
