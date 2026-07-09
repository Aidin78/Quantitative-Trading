from __future__ import annotations

from src.api.services.config_service import reset_provider_config, write_provider_config
from src.providers.metadata import get_provider_metadata


def test_provider_metadata_has_defaults_for_all_builtins() -> None:
    for provider_id in (
        "ema_crossover",
        "rsi_divergence",
        "macd_momentum",
        "adx_trend_strength",
        "bollinger_reversion",
        "supertrend_trend",
    ):
        meta = get_provider_metadata(provider_id)
        assert meta is not None
        assert meta.rules
        assert meta.default_config["params"]


def test_reset_provider_config_restores_defaults(tmp_path, monkeypatch) -> None:
    import src.api.services.config_service as config_service
    from src.engine.config import resolve_config_dir

    repo_config = resolve_config_dir()
    providers_src = repo_config / "providers"
    providers_dst = tmp_path / "providers"
    providers_dst.mkdir(parents=True)
    for path in providers_src.glob("*.yaml"):
        (providers_dst / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(config_service, "resolve_config_dir", lambda: tmp_path)

    write_provider_config(
        "ema_crossover",
        {"params": {"min_confidence": 0.99, "require_trend": False}},
    )
    restored = reset_provider_config("ema_crossover")
    defaults = get_provider_metadata("ema_crossover")
    assert defaults is not None
    assert (
        restored["params"]["min_confidence"] == defaults.default_config["params"]["min_confidence"]
    )
    assert restored["params"]["require_trend"] == defaults.default_config["params"]["require_trend"]
