"""Provider edge scorecard: solo/family backtests and keep/watch/drop verdicts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from src.core.contracts.execution import FillModel
from src.execution.config import load_default_fill_model
from src.validation.optimization_space import PROVIDER_ENABLED_KEYS
from src.validation.optimization_windows import split_holdout, split_train_test
from src.validation.trial_config import (
    build_engine_config_from_trial,
    build_execution_config_from_trial,
    build_features_config_from_trial,
    build_provider_overrides,
)

ScorecardMode = Literal["full", "pass2"]
Verdict = Literal["keep", "watch", "drop"]

TREND_ENABLED_KEYS = (
    "ema_enabled",
    "macd_enabled",
    "adx_enabled",
    "st_enabled",
    "ms_enabled",
)
REVERSION_ENABLED_KEYS = (
    "bb_enabled",
    "rsi_enabled",
)
FLOW_ENABLED_KEYS = ("vol_enabled",)

PROVIDER_SOLO_LABELS: dict[str, str] = {
    "ema_enabled": "EMA",
    "rsi_enabled": "RSI",
    "macd_enabled": "MACD",
    "adx_enabled": "ADX",
    "bb_enabled": "BB",
    "st_enabled": "ST",
    "vol_enabled": "VOL",
    "ms_enabled": "MS",
}

# Same fixed params as Pass 2 / provider discovery defaults.
BASE_PARAMS: dict[str, Any] = {
    "min_confidence": 0.65,
    "min_risk_reward": 1.2,
    "min_agreeing_providers": 1,
    "sl_atr_mult": 1.5,
    "tp_atr_mult": 3.0,
    "max_bars_in_trade": 24,
    "oversold": 30,
    "overbought": 70,
    "risk_pct_per_trade": 1.0,
    "min_atr_pct": 0.3,
    "session_preset": "all",
    "max_signals_per_day": 10,
    "ema_fast": 12,
    "ema_slow": 26,
    "rsi_period": 14,
    "ema_weight": 1.0,
    "rsi_weight": 1.0,
    "ema_enabled": 0,
    "rsi_enabled": 0,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal_period": 9,
    "macd_weight": 1.0,
    "macd_enabled": 0,
    "require_signal_align": 1,
    "min_histogram_slope": 0.0,
    "adx_period": 14,
    "adx_weight": 1.0,
    "adx_enabled": 0,
    "min_adx": 25,
    "min_di_spread": 5,
    "adx_require_trend": 0,
    "bb_period": 20,
    "bb_std": 2.0,
    "bb_weight": 1.0,
    "bb_enabled": 0,
    "bb_avoid_high_vol": 1,
    "bb_max_adx": 0,
    "st_period": 10,
    "st_multiplier": 3.0,
    "st_weight": 1.0,
    "st_enabled": 0,
    "st_require_trend": 0,
    "vol_period": 20,
    "vol_weight": 1.0,
    "vol_enabled": 0,
    "min_cmf": 0.05,
    "min_volume_ratio": 1.2,
    "vol_require_price_align": 1,
    "ms_pivot_bars": 5,
    "ms_weight": 1.0,
    "ms_enabled": 0,
    "ms_require_bos": 1,
    "ms_require_trend": 0,
}

PASS2_CONFIGS: list[tuple[str, dict[str, Any]]] = [
    ("A_EMA_only_agree1", {"ema_enabled": 1, "bb_enabled": 0, "min_agreeing_providers": 1}),
    ("B_BB_only_agree1", {"ema_enabled": 0, "bb_enabled": 1, "min_agreeing_providers": 1}),
    ("C_EMA_BB_agree1", {"ema_enabled": 1, "bb_enabled": 1, "min_agreeing_providers": 1}),
    ("D_EMA_BB_agree2", {"ema_enabled": 1, "bb_enabled": 1, "min_agreeing_providers": 2}),
]

_MIN_TRAIN_TRADES_KEEP = 20
_MIN_HOLDOUT_TRADES_KEEP = 10


def _solo_configs() -> list[tuple[str, dict[str, Any]]]:
    configs: list[tuple[str, dict[str, Any]]] = []
    for key, label in PROVIDER_SOLO_LABELS.items():
        overrides = {k: 0 for k in PROVIDER_ENABLED_KEYS}
        overrides[key] = 1
        overrides["min_agreeing_providers"] = 1
        configs.append((f"solo_{label}_agree1", overrides))
    return configs


FULL_CONFIGS: list[tuple[str, dict[str, Any]]] = [
    *_solo_configs(),
    *PASS2_CONFIGS,
    (
        "trend_EMA_MACD_ADX_agree1",
        {
            "ema_enabled": 1,
            "macd_enabled": 1,
            "adx_enabled": 1,
            "rsi_enabled": 0,
            "bb_enabled": 0,
            "st_enabled": 0,
            "vol_enabled": 0,
            "ms_enabled": 0,
            "min_agreeing_providers": 1,
        },
    ),
    (
        "reversion_BB_RSI_agree1",
        {
            "ema_enabled": 0,
            "macd_enabled": 0,
            "adx_enabled": 0,
            "rsi_enabled": 1,
            "bb_enabled": 1,
            "st_enabled": 0,
            "vol_enabled": 0,
            "ms_enabled": 0,
            "min_agreeing_providers": 1,
        },
    ),
]


def configs_for_mode(mode: ScorecardMode) -> list[tuple[str, dict[str, Any]]]:
    if mode == "pass2":
        return list(PASS2_CONFIGS)
    return list(FULL_CONFIGS)


def enabled_keys_from_overrides(overrides: dict[str, Any]) -> list[str]:
    return [key for key in PROVIDER_ENABLED_KEYS if int(overrides.get(key, 0)) == 1]


def verdict_for_windows(
    train: dict[str, Any] | None,
    holdout: dict[str, Any] | None,
    *,
    min_train_trades: int = _MIN_TRAIN_TRADES_KEEP,
    min_holdout_trades: int = _MIN_HOLDOUT_TRADES_KEEP,
    min_return_pct: float = 0.0,
) -> Verdict:
    """Classify a config from train + holdout metrics."""
    train = train or {}
    holdout = holdout or {}
    train_ret = float(train.get("return_pct") or 0.0)
    holdout_ret = float(holdout.get("return_pct") or 0.0)
    train_trades = int(train.get("total_trades") or 0)
    holdout_trades = int(holdout.get("total_trades") or 0)

    holdout_ok = holdout_ret >= min_return_pct and holdout_trades >= min_holdout_trades
    train_ok = train_ret >= min_return_pct and train_trades >= min_train_trades

    if train_ok and holdout_ok:
        return "keep"
    if holdout_ok and train_ret < min_return_pct:
        return "watch"
    return "drop"


def extract_window_metrics(result: Any) -> dict[str, Any]:
    outcome = result.outcome_metrics or {}
    return {
        "return_pct": outcome.get("return_pct"),
        "total_trades": outcome.get("total_trades"),
        "win_rate": outcome.get("win_rate"),
        "profit_factor": outcome.get("profit_factor"),
        "sharpe_ratio": outcome.get("sharpe_ratio"),
        "max_drawdown_pct": outcome.get("max_drawdown_pct"),
        "optimization_score": outcome.get("optimization_score", outcome.get("score")),
        "ending_equity": outcome.get("ending_equity"),
    }


def split_scorecard_windows(
    start: datetime,
    end: datetime,
    *,
    holdout_ratio: float = 0.2,
    train_ratio: float = 0.7,
) -> dict[str, tuple[datetime, datetime]]:
    (opt_start, opt_end), holdout = split_holdout(start, end, holdout_ratio=holdout_ratio)
    (train_start, train_end), (test_start, test_end) = split_train_test(
        opt_start, opt_end, train_ratio=train_ratio
    )
    windows: dict[str, tuple[datetime, datetime]] = {
        "train": (train_start, train_end),
        "test": (test_start, test_end),
    }
    if holdout is not None:
        windows["holdout"] = holdout
    return windows


def build_scorecard_payload(
    rows: list[dict[str, Any]],
    *,
    mode: ScorecardMode,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    windows: dict[str, tuple[datetime, datetime]],
) -> dict[str, Any]:
    """Attach verdicts and keep shortlist to scored config rows."""
    scored: list[dict[str, Any]] = []
    keep_keys: set[str] = set()

    for row in rows:
        overrides = row.get("params_overrides") or {}
        enabled = enabled_keys_from_overrides(overrides)
        verdict = verdict_for_windows(row.get("train"), row.get("holdout"))
        entry = {
            **row,
            "enabled_providers": enabled,
            "verdict": verdict,
        }
        scored.append(entry)
        # Shortlist only from solo keep configs (stable unit of discovery).
        name = str(row.get("config") or "")
        if verdict == "keep" and name.startswith("solo_"):
            keep_keys.update(enabled)

    return {
        "mode": mode,
        "symbol": symbol,
        "timeframe": timeframe,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "windows": {
            name: (w_start.isoformat(), w_end.isoformat())
            for name, (w_start, w_end) in windows.items()
        },
        "configs": scored,
        "keep_shortlist": sorted(keep_keys),
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


def load_keep_shortlist(path: Path | str) -> list[str]:
    """Load keep_shortlist enable-keys from a scorecard JSON file."""
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = data.get("keep_shortlist") or []
    return [str(key) for key in raw if key in PROVIDER_ENABLED_KEYS]


async def run_window_validation(
    *,
    params: dict[str, Any],
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    fill_model: FillModel | None = None,
) -> dict[str, Any]:
    engine_config = build_engine_config_from_trial(params)
    execution_config = build_execution_config_from_trial(params)
    features_config = build_features_config_from_trial(params)
    provider_overrides = build_provider_overrides(params)

    import src.validation.job_runner as job_runner_mod
    from src.validation.job_runner import run_validation_job

    original = job_runner_mod.load_default_fill_model
    if fill_model is not None:

        def _override(_config_dir=None):  # noqa: ANN001
            return fill_model

        job_runner_mod.load_default_fill_model = _override  # type: ignore[assignment]
    try:
        result = await run_validation_job(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start.date().isoformat(),
            end_date=end.date().isoformat(),
            source="exchange",
            persist_db=False,
            engine_config=engine_config,
            provider_overrides=provider_overrides,
            execution_config=execution_config,
            features_config=features_config,
        )
    finally:
        job_runner_mod.load_default_fill_model = original  # type: ignore[assignment]

    return extract_window_metrics(result)


async def run_scorecard(
    *,
    start: datetime,
    end: datetime,
    mode: ScorecardMode = "full",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    holdout_ratio: float = 0.2,
    train_ratio: float = 0.7,
    fee_sensitivity: bool = True,
) -> dict[str, Any]:
    windows = split_scorecard_windows(
        start, end, holdout_ratio=holdout_ratio, train_ratio=train_ratio
    )
    print(
        "Windows:",
        {k: (v[0].date().isoformat(), v[1].date().isoformat()) for k, v in windows.items()},
        flush=True,
    )

    rows: list[dict[str, Any]] = []
    for name, overrides in configs_for_mode(mode):
        params = {**BASE_PARAMS, **overrides}
        print(f"\n=== {name} ===", flush=True)
        row: dict[str, Any] = {"config": name, "params_overrides": overrides}
        for window_name, (w_start, w_end) in windows.items():
            print(f"  running {window_name}…", flush=True)
            metrics = await run_window_validation(
                params=params,
                symbol=symbol,
                timeframe=timeframe,
                start=w_start,
                end=w_end,
            )
            row[window_name] = metrics
            print(
                f"  {window_name}: ret={metrics['return_pct']} "
                f"trades={metrics['total_trades']} "
                f"sharpe={metrics.get('sharpe_ratio')} "
                f"score={metrics['optimization_score']}",
                flush=True,
            )
        rows.append(row)

        if fee_sensitivity and name == "C_EMA_BB_agree1":
            base_fill = load_default_fill_model()
            halved = FillModel(
                model_id=f"{base_fill.model_id}_half",
                slippage_bps=base_fill.slippage_bps / 2,
                fee_bps=base_fill.fee_bps / 2,
                fill_at=base_fill.fill_at,
            )
            print("\n=== C_EMA_BB_agree1 fees_halved ===", flush=True)
            fee_overrides = {**overrides, "fee_note": "half slip+fee"}
            fee_row: dict[str, Any] = {
                "config": "C_EMA_BB_agree1_fees_halved",
                "params_overrides": fee_overrides,
            }
            for window_name, (w_start, w_end) in windows.items():
                print(f"  running {window_name}…", flush=True)
                metrics = await run_window_validation(
                    params=params,
                    symbol=symbol,
                    timeframe=timeframe,
                    start=w_start,
                    end=w_end,
                    fill_model=halved,
                )
                fee_row[window_name] = metrics
                print(
                    f"  {window_name}: ret={metrics['return_pct']} "
                    f"trades={metrics['total_trades']} "
                    f"score={metrics['optimization_score']}",
                    flush=True,
                )
            rows.append(fee_row)

    return build_scorecard_payload(
        rows,
        mode=mode,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        windows=windows,
    )


async def evaluate_params_scorecard(
    params: dict[str, Any],
    *,
    start: datetime,
    end: datetime,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    holdout_ratio: float = 0.2,
    train_ratio: float = 0.7,
) -> dict[str, Any]:
    """Run train/test/holdout for fixed trial params and attach a keep/watch/drop verdict."""
    windows = split_scorecard_windows(
        start, end, holdout_ratio=holdout_ratio, train_ratio=train_ratio
    )
    row: dict[str, Any] = {
        "config": "tuned_params",
        "params_overrides": dict(params),
    }
    for window_name, (w_start, w_end) in windows.items():
        print(f"  rescore {window_name}…", flush=True)
        metrics = await run_window_validation(
            params=params,
            symbol=symbol,
            timeframe=timeframe,
            start=w_start,
            end=w_end,
        )
        row[window_name] = metrics
        print(
            f"  {window_name}: ret={metrics['return_pct']} "
            f"trades={metrics['total_trades']} "
            f"score={metrics['optimization_score']}",
            flush=True,
        )
    verdict = verdict_for_windows(row.get("train"), row.get("holdout"))
    row["verdict"] = verdict
    row["enabled_providers"] = enabled_keys_from_overrides(params)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "windows": {
            name: (w_start.isoformat(), w_end.isoformat())
            for name, (w_start, w_end) in windows.items()
        },
        "result": row,
        "verdict": verdict,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


def print_scorecard_summary(payload: dict[str, Any]) -> None:
    print("\n=== SUMMARY TABLE ===", flush=True)
    hdr = (
        f"{'config':<32} {'verdict':<6} {'window':<8} "
        f"{'return%':>10} {'trades':>8} {'win%':>8} {'sharpe':>8} {'score':>10}"
    )
    print(hdr, flush=True)
    print("-" * len(hdr), flush=True)
    for row in payload.get("configs") or []:
        verdict = row.get("verdict", "")
        for window_name in ("train", "test", "holdout"):
            m = row.get(window_name) or {}
            win_rate = m.get("win_rate")
            win_pct = f"{float(win_rate) * 100:.1f}" if win_rate is not None else None
            print(
                f"{row['config']:<32} {verdict:<6} {window_name:<8} "
                f"{m.get('return_pct'):>10} {m.get('total_trades'):>8} "
                f"{win_pct:>8} {m.get('sharpe_ratio'):>8} "
                f"{m.get('optimization_score'):>10}",
                flush=True,
            )
    shortlist = payload.get("keep_shortlist") or []
    print(f"\nkeep_shortlist: {shortlist if shortlist else '(empty)'}", flush=True)
