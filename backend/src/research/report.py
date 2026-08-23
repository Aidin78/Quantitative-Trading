"""Shared report building for the signal-research CLI: JSON payload + text summary."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from src.research.classification_phase import ClassificationResult
from src.research.direction_phase import DirectionResult
from src.research.magnitude_phase import MagnitudeResult


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
        print(
            f"  {row['base_signal']} + {row['filter_name']}"
            f" @p{row['filter_threshold_percentile']:.0f}, h={row['horizon']}: "
            f"win_rate {row['baseline_win_rate']:.1f}% -> {row['filtered_win_rate']:.1f}%"
            f" (+{row['win_rate_improvement_pp']:.1f}pp, n={row['filtered_trades']})",
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
