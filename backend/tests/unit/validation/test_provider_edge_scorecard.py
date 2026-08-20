"""Unit tests for provider edge scorecard verdicts and shortlist."""

from __future__ import annotations

from datetime import UTC, datetime

from src.validation.provider_edge_scorecard import (
    build_scorecard_payload,
    configs_for_mode,
    enabled_keys_from_overrides,
    verdict_for_windows,
)


def test_verdict_keep() -> None:
    assert (
        verdict_for_windows(
            {"return_pct": 2.0, "total_trades": 40},
            {"return_pct": 1.0, "total_trades": 15},
        )
        == "keep"
    )


def test_verdict_watch_when_holdout_ok_train_negative() -> None:
    assert (
        verdict_for_windows(
            {"return_pct": -5.0, "total_trades": 40},
            {"return_pct": 1.0, "total_trades": 15},
        )
        == "watch"
    )


def test_verdict_drop_when_holdout_negative() -> None:
    assert (
        verdict_for_windows(
            {"return_pct": 2.0, "total_trades": 40},
            {"return_pct": -3.0, "total_trades": 15},
        )
        == "drop"
    )


def test_configs_for_mode() -> None:
    pass2 = configs_for_mode("pass2")
    assert len(pass2) == 4
    assert pass2[0][0].startswith("A_")
    full = configs_for_mode("full")
    assert len(full) > len(pass2)
    names = [name for name, _ in full]
    assert "solo_EMA_agree1" in names
    assert "trend_EMA_MACD_ADX_agree1" in names
    assert "reversion_BB_RSI_agree1" in names


def test_build_scorecard_payload_shortlist_from_solo_keep() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2026, 7, 18, tzinfo=UTC)
    windows = {
        "train": (start, start),
        "test": (start, start),
        "holdout": (start, end),
    }
    rows = [
        {
            "config": "solo_EMA_agree1",
            "params_overrides": {"ema_enabled": 1, "bb_enabled": 0},
            "train": {"return_pct": 1.0, "total_trades": 30},
            "holdout": {"return_pct": 0.5, "total_trades": 12},
        },
        {
            "config": "C_EMA_BB_agree1",
            "params_overrides": {"ema_enabled": 1, "bb_enabled": 1},
            "train": {"return_pct": 1.0, "total_trades": 30},
            "holdout": {"return_pct": 0.5, "total_trades": 12},
        },
        {
            "config": "solo_BB_agree1",
            "params_overrides": {"ema_enabled": 0, "bb_enabled": 1},
            "train": {"return_pct": -2.0, "total_trades": 30},
            "holdout": {"return_pct": -1.0, "total_trades": 12},
        },
    ]
    payload = build_scorecard_payload(
        rows,
        mode="full",
        symbol="BTC/USDT",
        timeframe="1h",
        start=start,
        end=end,
        windows=windows,
    )
    assert payload["keep_shortlist"] == ["ema_enabled"]
    assert payload["configs"][0]["verdict"] == "keep"
    assert payload["configs"][1]["verdict"] == "keep"
    assert payload["configs"][2]["verdict"] == "drop"
    assert enabled_keys_from_overrides(rows[0]["params_overrides"]) == ["ema_enabled"]
