#!/usr/bin/env python3
"""Register the managed long-core strategy through the formal governance path.

Item 4 of the "remaining (optional)" list in
docs/development/managed-long-core-findings.md: run it through
``ConfigRevision`` / ``Experiment`` / ``Candidate`` rather than only a
script, and put it in front of the deterministic ``CandidateEvaluator``.

What this does (all against a local sqlite governance DB, not Postgres):
  1. builds + saves a real ``ConfigRevision`` (label ``core_long_v1``) whose
     config_bundle captures the strategy: only ``core_long`` enabled,
     ``features.core_long.yaml``, ``vol_target_atr_pct`` on the engine,
     ``long_only`` + ``exposure_pct_per_trade`` on execution.
  2. creates an ``Experiment`` under it (BTC/USDT + ETH/USDT, 1d).
  3. runs a 3-fold anchored walk-forward in-sample + a held-out tail on both
     symbols, and assembles an ``OptimizationResult`` (fold scores/std for the
     stability gate, merged holdout outcome for the sample/regime gates).
  4. records an ``ExperimentRun`` with the full-history metrics_summary.
  5. creates a ``Candidate`` (state ``candidate``) and runs
     ``run_candidate_evaluation`` — the deterministic accept/reject policy.
  6. on ``accepted`` only, promotes the candidate to ``challenger``.

The candidate always gets *created* — that is the "promoted to candidate" the
task asks for. Whether it can advance further is the evaluator's call, printed
verbatim at the end.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from scripts.run_core_long_validation import (  # noqa: E402
    _ALL_PROVIDERS,
    _engine_config,
)
from src.core.contracts.governance import ConfigRevision  # noqa: E402
from src.core.contracts.state import RiskLimits  # noqa: E402
from src.db.base import Base  # noqa: E402
from src.execution.config import ValidationExecutionConfig  # noqa: E402
from src.features.config import load_features_config_file  # noqa: E402
from src.governance.candidate_store import (  # noqa: E402
    create_candidate,
    promote_candidate,
    run_candidate_evaluation,
)
from src.governance.experiment_store import (  # noqa: E402
    complete_experiment_run,
    create_experiment,
    create_experiment_run,
)
from src.governance.revision_store import save_revision  # noqa: E402
from src.validation.job_runner import run_validation_job  # noqa: E402
from src.validation.optimization_scoring import OptimizationResult, TrialResult  # noqa: E402
from src.validation.walk_forward import build_anchored_walk_forward_windows  # noqa: E402

_SYMBOLS = ("BTC/USDT", "ETH/USDT")
_RISK_LIMITS = RiskLimits(
    max_daily_drawdown_pct=100.0,
    max_open_positions=1,
    max_exposure_pct=100.0,
    max_consecutive_losses=100_000,
)


def _strategy_params(sma: str, atr_pct: float, cap: float) -> dict[str, Any]:
    return {
        "sma_indicator": sma,
        "vol_target_atr_pct": atr_pct,
        "vol_target_cap": cap,
        "long_only": True,
        "exposure_pct_per_trade": 100.0,
        "regime_off_side": "SELL",
    }


def _provider_overrides(sma: str) -> dict[str, dict]:
    overrides: dict[str, dict] = {p: {"enabled": False} for p in _ALL_PROVIDERS}
    overrides["core_long"] = {
        "enabled": True,
        "sma_indicator": sma,
        "confidence": 0.9,
        "min_confidence": 0.6,
        "regime_off_side": "SELL",
        "use_atr_stops": True,
        "sl_atr_mult": 1000.0,
        "tp_atr_mult": 1000.0,
    }
    return overrides


def _config_revision(params: dict[str, Any]) -> ConfigRevision:
    features_path = _BACKEND.parent / "config" / "features.core_long.yaml"
    provider_path = _BACKEND.parent / "config" / "providers" / "core_long.yaml"
    features_hash = hashlib.sha256(features_path.read_bytes()).hexdigest()
    provider_hash = hashlib.sha256(provider_path.read_bytes()).hexdigest()
    digest = hashlib.sha256(
        f"core_long_v1:{sorted(params.items())}:{features_hash}:{provider_hash}".encode()
    ).hexdigest()[:16]
    return ConfigRevision(
        revision_id=f"rev_{digest}",
        created_at=datetime.now(UTC),
        engine_config_hash=digest,
        features_config_hash=features_hash[:16],
        providers_config_hash=provider_hash[:16],
        fill_model_id="default",
        risk_limits_hash=hashlib.sha256(str(_RISK_LIMITS.model_dump()).encode()).hexdigest()[:16],
        label="core_long_v1",
        config_bundle={
            "strategy": "managed_long_core",
            "doc": "docs/development/managed-long-core-findings.md",
            "params": params,
            "providers": {"core_long": {"enabled": True}},
            "features_config": "config/features.core_long.yaml",
            "risk_limits": _RISK_LIMITS.model_dump(),
            "note": (
                "Trend + vol-targeting risk-premium harvest, not a directional edge. "
                "Regime-off = go to cash (long_only)."
            ),
        },
    )


async def _run_span(
    symbol: str,
    start: datetime,
    end: datetime,
    features_config,
    params: dict[str, Any],
) -> dict[str, Any]:
    exec_config = ValidationExecutionConfig(
        max_bars_in_trade=1_000_000,
        risk_pct_per_trade=1.0,
        long_only=True,
        exposure_pct_per_trade=params["exposure_pct_per_trade"],
    )
    result = await run_validation_job(
        symbol=symbol,
        timeframe="1d",
        start_date=start.date().isoformat(),
        end_date=end.date().isoformat(),
        source="exchange",
        persist_db=False,
        retain_events=True,
        engine_config=_engine_config(params["vol_target_atr_pct"], params["vol_target_cap"]),
        provider_overrides=_provider_overrides(params["sma_indicator"]),
        execution_config=exec_config,
        features_config=features_config,
        risk_limits=_RISK_LIMITS,
    )
    return result.outcome_metrics or {}


def _merge_holdout(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum trades and merge regime buckets across the per-symbol holdout runs."""
    merged: dict[str, Any] = {
        "total_trades": sum(int(o.get("total_trades", 0)) for o in outcomes),
        "return_pct": (
            sum(float(o.get("return_pct", 0.0)) for o in outcomes) / len(outcomes)
            if outcomes
            else 0.0
        ),
    }
    by_regime: dict[str, dict[str, float]] = {}
    for outcome in outcomes:
        buckets = (outcome.get("regime_analysis") or {}).get("by_regime") or {}
        for name, stats in buckets.items():
            acc = by_regime.setdefault(name, {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})
            for key in ("trades", "wins", "losses", "pnl"):
                acc[key] += stats.get(key, 0)
    merged["regime_analysis"] = {"by_regime": by_regime}
    return merged


async def _run() -> int:
    parser = argparse.ArgumentParser(description="Managed long-core governance run")
    parser.add_argument("--sma", default="sma_150")
    parser.add_argument("--vol-target-atr-pct", type=float, default=2.5)
    parser.add_argument("--vol-target-cap", type=float, default=1.5)
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-08-27")
    parser.add_argument("--holdout-start", default="2024-01-01")
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument(
        "--db",
        default=str(_BACKEND / "data" / "governance_core_long.db"),
        help="sqlite governance DB path",
    )
    args = parser.parse_args()

    params = _strategy_params(args.sma, args.vol_target_atr_pct, args.vol_target_cap)
    features_config = load_features_config_file(
        _BACKEND.parent / "config" / "features.core_long.yaml"
    )
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    holdout_start = datetime.fromisoformat(args.holdout_start).replace(tzinfo=UTC)

    print(f"strategy params: {params}", flush=True)

    # ---- walk-forward folds (in-sample), test segment scores per fold ----
    windows = build_anchored_walk_forward_windows(
        start, holdout_start, windows=args.folds, train_ratio=0.7
    )
    fold_scores: list[float] = []
    for window in windows:
        per_symbol: list[float] = []
        for symbol in _SYMBOLS:
            outcome = await _run_span(
                symbol, window.test_start, window.test_end, features_config, params
            )
            per_symbol.append(float(outcome.get("optimization_score", 0.0)))
        fold_mean = sum(per_symbol) / len(per_symbol)
        fold_scores.append(fold_mean)
        print(
            f"  fold {window.index}: {window.test_start.date()}..{window.test_end.date()} "
            f"score={fold_mean:.2f}",
            flush=True,
        )
    mean = sum(fold_scores) / len(fold_scores)
    variance = sum((s - mean) ** 2 for s in fold_scores) / max(1, len(fold_scores) - 1)
    fold_std = variance**0.5

    # ---- holdout tail on both symbols ----
    holdout_outcomes: list[dict[str, Any]] = []
    for symbol in _SYMBOLS:
        outcome = await _run_span(symbol, holdout_start, end, features_config, params)
        holdout_outcomes.append(outcome)
        print(
            f"  holdout {symbol}: trades={outcome.get('total_trades')} "
            f"return_pct={outcome.get('return_pct')}",
            flush=True,
        )
    holdout = _merge_holdout(holdout_outcomes)
    h_trades = int(holdout["total_trades"])
    h_return = float(holdout["return_pct"])
    holdout_valid = h_trades >= 10 and h_return >= 0.0

    # ---- full-history metrics_summary for the ExperimentRun ----
    full_summary: dict[str, float] = {}
    for symbol in _SYMBOLS:
        outcome = await _run_span(symbol, start, end, features_config, params)
        tag = symbol.split("/")[0].lower()
        full_summary[f"{tag}_total_trades"] = float(outcome.get("total_trades", 0))
        full_summary[f"{tag}_return_pct"] = float(outcome.get("return_pct", 0))
        full_summary[f"{tag}_max_drawdown_pct"] = float(outcome.get("max_drawdown_pct", 0))
        full_summary[f"{tag}_sharpe_ratio"] = float(outcome.get("sharpe_ratio", 0))

    result = OptimizationResult(
        sweep_id=f"sweep_core_long_{datetime.now(UTC):%Y%m%d}",
        symbol="BTC/USDT+ETH/USDT",
        timeframe="1d",
        train_start=start,
        train_end=holdout_start,
        test_start=windows[-1].test_start,
        test_end=holdout_start,
        holdout_start=holdout_start,
        holdout_end=end,
        holdout_outcome=holdout,
        holdout_valid=holdout_valid,
        best=TrialResult(
            trial_id="trial_core_long_v1",
            params=params,
            train_score=mean,
            train_outcome={},
            test_score=mean,
            test_outcome=holdout,
            fold_scores=fold_scores,
            fold_std=fold_std,
        ),
    )

    # ---- persist to the governance DB ----
    engine = create_async_engine(f"sqlite+aiosqlite:///{args.db}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        revision = _config_revision(params)
        await save_revision(session, revision)
        experiment = await create_experiment(
            session,
            revision_id=revision.revision_id,
            name="managed_long_core",
            mode="validation",
            symbols=_SYMBOLS,
            timeframes=("1d",),
            description="Trend regime gate + volatility targeting; risk-premium harvest.",
            hypothesis=(
                "A trend-based risk-off switch plus vol-targeted sizing turns a "
                "buy-and-hold crypto core into a materially better risk-adjusted "
                "vehicle (roughly half the drawdown, higher Calmar/Sharpe)."
            ),
        )
        run = await create_experiment_run(
            session, experiment_id=experiment.experiment_id, revision_id=revision.revision_id
        )
        await complete_experiment_run(
            session, run.run_id, status="completed", metrics_summary=full_summary
        )
        candidate = await create_candidate(session, experiment_id=experiment.experiment_id)
        evaluation = await run_candidate_evaluation(session, candidate.candidate_id, result)
        await session.commit()

        promoted_state = candidate.state
        if evaluation is not None and evaluation.decision == "accepted":
            challenger = await promote_candidate(
                session, candidate.candidate_id, to_state="challenger"
            )
            await session.commit()
            promoted_state = challenger.state if challenger else promoted_state

    await engine.dispose()

    print("\n===== governance registration =====", flush=True)
    print(f"  db               : {args.db}", flush=True)
    print(f"  revision_id      : {revision.revision_id} ({revision.label})", flush=True)
    print(f"  experiment_id    : {experiment.experiment_id}", flush=True)
    print(f"  experiment_run   : {run.run_id}  metrics_summary={full_summary}", flush=True)
    print(f"  candidate_id     : {candidate.candidate_id}", flush=True)
    print("\n===== deterministic CandidateEvaluator =====", flush=True)
    print(
        f"  fold_scores={[round(s, 1) for s in fold_scores]} fold_std={fold_std:.2f}",
        flush=True,
    )
    print(
        f"  holdout: trades={h_trades} return_pct={h_return:.1f} valid={holdout_valid}",
        flush=True,
    )
    for check in evaluation.checks if evaluation else ():
        mark = "PASS" if check.passed else "FAIL"
        print(f"  [{mark}] {check.check_name}: {check.detail}", flush=True)
    if evaluation:
        print(
            f"\n  decision: {evaluation.decision.upper()} - {evaluation.decision_reason}",
            flush=True,
        )
    print(f"  candidate final state: {promoted_state}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
