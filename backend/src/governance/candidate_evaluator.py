from __future__ import annotations

from src.core.contracts.governance import CandidateCheck
from src.validation.optimization_scoring import OptimizationResult

# Below this, "loss concentrated in one regime" and "loss concentrated
# elsewhere" are indistinguishable from noise -- there just aren't enough
# trades in the regime breakdown to say anything.
MIN_TRADES_FOR_REGIME_CHECK = 20

# A single regime accounting for more than this share of all trades is
# treated as evidence the result may not generalize across market
# conditions, not proof it doesn't -- see the check's detail message.
MAX_SINGLE_REGIME_SHARE = 0.8


def _check_out_of_sample(result: OptimizationResult) -> CandidateCheck:
    """Reuses run_optimization's own holdout_valid gate rather than
    re-deriving OOS validity from raw metrics -- that gate already enforces
    min trades and min return on data the optimizer never trained or
    selected on.
    """
    return CandidateCheck(
        check_name="out_of_sample",
        passed=result.holdout_valid,
        detail=(
            "Holdout period met minimum trades and return thresholds"
            if result.holdout_valid
            else "Holdout period failed minimum trades/return thresholds "
            "(see OptimizationResult.selection_message for the exact numbers)"
        ),
    )


def _check_minimum_sample(result: OptimizationResult) -> CandidateCheck:
    trades = int((result.holdout_outcome or {}).get("total_trades", 0))
    passed = trades >= MIN_TRADES_FOR_REGIME_CHECK
    return CandidateCheck(
        check_name="minimum_sample",
        passed=passed,
        detail=f"{trades} holdout trades",
        current_value=float(trades),
        threshold=float(MIN_TRADES_FOR_REGIME_CHECK),
    )


def _check_fold_stability(result: OptimizationResult) -> CandidateCheck:
    """Walk-forward fold_std is already computed by optimization_scoring and
    penalized in composite_score during selection -- this check just makes
    the same signal visible as an explicit accept/reject gate rather than
    something folded invisibly into one scalar score. Absent (no
    walk-forward run) is reported as not_evaluated, never as a pass.
    """
    best = result.best or result.fallback_trial
    if best is None or best.fold_std is None:
        return CandidateCheck(
            check_name="fold_stability",
            passed=False,
            detail="not_evaluated: no walk-forward folds were run for this candidate",
        )
    fold_std = best.fold_std
    fold_mean = sum(best.fold_scores) / len(best.fold_scores) if best.fold_scores else 0.0
    threshold = abs(fold_mean) * 0.5 + 5.0
    passed = fold_std <= threshold
    return CandidateCheck(
        check_name="fold_stability",
        passed=passed,
        detail=f"fold_std={fold_std:.2f} across {len(best.fold_scores)} folds",
        current_value=fold_std,
        threshold=threshold,
    )


def _check_regime_concentration(result: OptimizationResult) -> CandidateCheck:
    """Guards against a candidate whose entire apparent edge lives in one
    regime bucket from the holdout period's regime_analysis (added in the
    failure-analysis phase) -- a result that only works in one market
    condition is not the same claim as a result that is robust across them.
    """
    outcome = result.holdout_outcome or {}
    by_regime = (outcome.get("regime_analysis") or {}).get("by_regime") or {}
    total_trades = sum(bucket.get("trades", 0) for bucket in by_regime.values())
    if total_trades < MIN_TRADES_FOR_REGIME_CHECK:
        return CandidateCheck(
            check_name="regime_concentration",
            passed=False,
            detail=f"not_evaluated: only {total_trades} attributed holdout trades",
        )
    max_share = max(bucket.get("trades", 0) / total_trades for bucket in by_regime.values())
    passed = max_share <= MAX_SINGLE_REGIME_SHARE
    return CandidateCheck(
        check_name="regime_concentration",
        passed=passed,
        detail=f"largest single regime accounts for {max_share:.0%} of holdout trades",
        current_value=max_share,
        threshold=MAX_SINGLE_REGIME_SHARE,
    )


def evaluate_candidate(result: OptimizationResult) -> tuple[tuple[CandidateCheck, ...], str, str]:
    """Deterministic acceptance policy over an OptimizationResult's holdout
    performance. No LLM, no natural-language reasoning, no in-sample metric
    anywhere in this function -- every check reads only holdout_outcome or
    the walk-forward fold data that was itself computed on data the trial
    was not selected against.

    Returns (checks, decision, decision_reason). Deliberately does not decide
    promotion (candidate -> challenger -> champion) by itself -- that is a
    separate, human/process decision layered on top of "did this candidate
    pass its checks," which is all this function answers.
    """
    checks = (
        _check_out_of_sample(result),
        _check_minimum_sample(result),
        _check_fold_stability(result),
        _check_regime_concentration(result),
    )
    passed = all(check.passed for check in checks)
    if passed:
        return checks, "accepted", "All checks passed."
    failed_names = [check.check_name for check in checks if not check.passed]
    return checks, "rejected", f"Failed: {', '.join(failed_names)}"
