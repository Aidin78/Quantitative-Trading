"""Shared report building for the signal-research CLI: JSON payload + text summary."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from src.research.classification_phase import ClassificationResult
from src.research.direction_phase import DirectionResult
from src.research.magnitude_phase import MagnitudeResult
from src.research.stability_phase import (
    PercentileSweepResult,
    StabilityVerdict,
    SubWindowResult,
)


def build_direction_payload(results: list[DirectionResult]) -> dict[str, Any]:
    passing = [r.name for r in results if r.passes_threshold]
    return {
        "phase": 1,
        "name": "direction_prediction",
        "candidates": [asdict(r) for r in results],
        "passing_candidates": passing,
        "verdict": (
            f"{len(passing)} candidate(s) beat the 50% baseline with a real margin."
            if passing
            else "No candidate showed direction-prediction edge above the baseline threshold."
        ),
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


def build_magnitude_payload(results: list[MagnitudeResult]) -> dict[str, Any]:
    rows = []
    for r in results:
        rows.append(
            {
                "name": r.name,
                "corr_absret_by_horizon": r.corr_absret_by_horizon,
                "corr_maxrange_by_horizon": r.corr_maxrange_by_horizon,
                "decile_table": r.decile_table.to_dict(orient="records"),
            }
        )

    def _best_corr(r: MagnitudeResult) -> float:
        valid = [v for v in r.corr_absret_by_horizon.values() if v == v]  # noqa: PLR0124 (NaN filter)
        return max(valid, default=0.0)

    best = max(results, key=_best_corr, default=None)
    return {
        "phase": 2,
        "name": "magnitude_prediction",
        "predictors": rows,
        "verdict": (
            f"Best magnitude predictor: {best.name} (spearman up to {_best_corr(best):.3f})"
            if best is not None
            else "No predictors evaluated."
        ),
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


def build_classification_payload(results: list[ClassificationResult]) -> dict[str, Any]:
    passing_results = [r for r in results if r.passes_threshold]
    passing = [asdict(r) for r in passing_results]
    if passing_results:
        best_improvement = max(r.win_rate_improvement_pp for r in passing_results)
        verdict = (
            f"{len(passing)} magnitude-gated combination(s) passed the "
            f"win-rate improvement threshold (best: +{best_improvement:.1f}pp)."
        )
    else:
        verdict = "No magnitude-gated combination met the win-rate improvement threshold."
    return {
        "phase": 3,
        "name": "threshold_classification",
        "results": [asdict(r) for r in results],
        "passing_candidates": passing,
        "verdict": verdict,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


def build_stability_payload(
    *,
    base_signal: str,
    filter_name: str,
    horizon: int,
    sub_window_results: list[SubWindowResult],
    stability_verdict: StabilityVerdict,
    percentile_sweep: PercentileSweepResult | None,
    volatility_overlay: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "phase": "3b",
        "name": "candidate_stability",
        "base_signal": base_signal,
        "filter_name": filter_name,
        "horizon": horizon,
        "sub_windows": [asdict(r) for r in sub_window_results],
        "stability_verdict": asdict(stability_verdict),
        "percentile_sweep": (
            {
                "points": [
                    {
                        "percentile_threshold": p.percentile_threshold,
                        "train_stats": [asdict(r) for r in p.train_stats],
                        "holdout_stats": (
                            asdict(p.holdout_stats) if p.holdout_stats is not None else None
                        ),
                    }
                    for p in percentile_sweep.points
                ],
                "best_threshold_on_train": percentile_sweep.best_threshold_on_train,
                "best_threshold_rank_unstable": percentile_sweep.best_threshold_rank_unstable,
                "holdout_verdict_for_best": percentile_sweep.holdout_verdict_for_best,
            }
            if percentile_sweep is not None
            else None
        ),
        "volatility_overlay": (
            {name: asdict(stats) for name, stats in volatility_overlay.items()}
            if volatility_overlay is not None
            else None
        ),
        "verdict": (
            "Repeatable across sub-windows/regimes."
            if stability_verdict.passes_repeatability
            else "NOT repeatable — likely a single-window/regime artifact, not a real edge."
        ),
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


def print_stability_summary(payload: dict[str, Any]) -> None:
    print("\n=== PHASE 3b: CANDIDATE STABILITY ===", flush=True)
    print(
        f"  candidate: {payload['base_signal']} + {payload['filter_name']}, "
        f"h={payload['horizon']}",
        flush=True,
    )
    print(
        "  NOTE: max_dd below is peak-to-trough on a non-compounding sum of "
        "per-trade %returns (flat sizing) — a relative ranking tool, not an "
        "expected account drawdown. net_expectancy applies an approximate flat "
        "fee/slippage haircut, not a real fill simulation.",
        flush=True,
    )
    for row in payload["sub_windows"]:
        f = row["filtered_stats"]
        net = row["filtered_stats_net_fees"]
        print(
            f"  window {row['window_index'] + 1}/{row['n_windows']}: "
            f"improvement={row['win_rate_improvement_pp']:+.1f}pp n={f['trades']} "
            f"expectancy={f['expectancy']:.3f}% pf={f['profit_factor']:.2f} "
            f"avg_win={f['avg_win']:.3f}% avg_loss={f['avg_loss']:.3f}% "
            f"max_dd={f['max_drawdown_pct']:.2f}% "
            f"net_expectancy={net['expectancy']:.3f}% "
            f"regime_max_share={row['regime_concentration_share']:.0%}"
            f"{' [CONCENTRATED]' if row['regime_concentration_flag'] else ''}",
            flush=True,
        )
    print(f"\n{payload['stability_verdict']['detail']}", flush=True)
    print(payload["verdict"], flush=True)

    sweep = payload.get("percentile_sweep")
    if sweep:
        print("\n  --- percentile threshold sweep ---", flush=True)
        for point in sweep["points"]:
            train_imps = [
                r["win_rate_improvement_pp"]
                for r in point["train_stats"]
                if r["win_rate_improvement_pp"] == r["win_rate_improvement_pp"]  # not NaN
            ]
            avg_train = sum(train_imps) / len(train_imps) if train_imps else float("nan")
            holdout = point["holdout_stats"]
            holdout_imp = holdout["win_rate_improvement_pp"] if holdout else float("nan")
            print(
                f"    p{point['percentile_threshold']:.0f}: "
                f"avg_train_improvement={avg_train:+.1f}pp "
                f"holdout_improvement={holdout_imp:+.1f}pp",
                flush=True,
            )
        print(
            f"  best_threshold_on_train=p{sweep['best_threshold_on_train']}"
            if sweep["best_threshold_on_train"] is not None
            else "  best_threshold_on_train=(none eligible)",
            flush=True,
        )
        if sweep["best_threshold_rank_unstable"]:
            print(
                "  WARNING: best threshold's rank is not consistent across train "
                "sub-windows — likely overfitting, not a stable edge.",
                flush=True,
            )
        print(f"  holdout verdict: {sweep['holdout_verdict_for_best']}", flush=True)

    overlay = payload.get("volatility_overlay")
    if overlay:
        print("\n  --- ATR volatility filter/sizing overlay ---", flush=True)
        for name, stats in overlay.items():
            print(
                f"    {name}: n={stats['trades']} expectancy={stats['expectancy']:.3f}% "
                f"pf={stats['profit_factor']:.2f} max_dd={stats['max_drawdown_pct']:.2f}%",
                flush=True,
            )


def print_direction_summary(payload: dict[str, Any]) -> None:
    print("\n=== PHASE 1: DIRECTION PREDICTION ===", flush=True)
    for row in payload["candidates"]:
        acc = ", ".join(f"h={h}:{v:.2f}%" for h, v in row["accuracy_by_horizon"].items())
        mark = "PASS" if row["passes_threshold"] else "no edge"
        print(f"  [{mark:>7}] {row['name']:<40} {acc}  flips={row['flips']}", flush=True)
    print(f"\n{payload['verdict']}", flush=True)


def print_magnitude_summary(payload: dict[str, Any]) -> None:
    print("\n=== PHASE 2: MAGNITUDE PREDICTION ===", flush=True)
    for row in payload["predictors"]:
        corr = ", ".join(f"h={h}:{v:.3f}" for h, v in row["corr_absret_by_horizon"].items())
        print(f"  {row['name']:<32} {corr}", flush=True)
    print(f"\n{payload['verdict']}", flush=True)


def print_classification_summary(payload: dict[str, Any]) -> None:
    print("\n=== PHASE 3: THRESHOLD CLASSIFICATION ===", flush=True)
    for row in payload["passing_candidates"]:
        filtered = row["filtered_stats"]
        net = row["filtered_stats_net_fees"]
        print(
            f"  {row['base_signal']} + {row['filter_name']}"
            f" @p{row['filter_threshold_percentile']:.0f}, h={row['horizon']}: "
            f"win_rate {row['baseline_win_rate']:.1f}% -> {row['filtered_win_rate']:.1f}%"
            f" (+{row['win_rate_improvement_pp']:.1f}pp, n={row['filtered_trades']})",
            flush=True,
        )
        print(
            f"      expectancy={filtered['expectancy']:.3f}% "
            f"profit_factor={filtered['profit_factor']:.2f} "
            f"avg_win={filtered['avg_win']:.3f}% avg_loss={filtered['avg_loss']:.3f}% "
            f"max_dd={filtered['max_drawdown_pct']:.2f}% "
            f"| net_of_fees: expectancy={net['expectancy']:.3f}% "
            f"profit_factor={net['profit_factor']:.2f}",
            flush=True,
        )
    print(f"\n{payload['verdict']}", flush=True)
    if payload["passing_candidates"]:
        print(
            "\nTo validate under real fees/slippage/sizing, run Phase 4 manually via:"
            "\n  poetry run python scripts/run_provider_discovery.py "
            "--symbol <symbol> --timeframe <timeframe> --start <start> --end <end>"
            "\n(pass the matching provider + threshold as provider_overrides once wired"
            " into the target provider's config)",
            flush=True,
        )
