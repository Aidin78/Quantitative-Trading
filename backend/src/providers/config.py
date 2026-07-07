from __future__ import annotations

from pathlib import Path

import yaml

from src.providers.base import ProviderConfig


def load_provider_yaml(path: Path) -> ProviderConfig:
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return ProviderConfig(**raw)
