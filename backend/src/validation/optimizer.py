from __future__ import annotations

from src.validation.optimization_progress import ProgressCallback, ProgressEvent
from src.validation.optimization_runner import run_optimization
from src.validation.optimization_scoring import (
    OptimizationResult,
    TrialResult,
    _aggregate_fold_outcomes,
    assign_pareto_ranks,
    build_selection_message,
    composite_score,
    compute_stability,
    select_best,
)
from src.validation.optimization_space import (
    BB_SOLO_TUNING_SPACE,
    PROVIDER_DISCOVERY_CONSTRAINED_SPACE,
    PROVIDER_DISCOVERY_SPACE,
    PROVIDER_ENABLED_KEYS,
    TRIAL_PARAM_KEYS,
    OptimizationSpace,
    enabled_provider_labels,
    generate_trials,
    generate_trials_optuna,
    has_any_provider_enabled,
    has_compatible_provider_family,
    is_valid_provider_trial,
    refine_trials_around,
    space_requires_family_filter,
)
from src.validation.optimization_windows import split_holdout, split_train_test

__all__ = [
    "BB_SOLO_TUNING_SPACE",
    "PROVIDER_DISCOVERY_CONSTRAINED_SPACE",
    "PROVIDER_DISCOVERY_SPACE",
    "PROVIDER_ENABLED_KEYS",
    "TRIAL_PARAM_KEYS",
    "OptimizationResult",
    "OptimizationSpace",
    "ProgressCallback",
    "ProgressEvent",
    "TrialResult",
    "_aggregate_fold_outcomes",
    "assign_pareto_ranks",
    "build_selection_message",
    "composite_score",
    "compute_stability",
    "enabled_provider_labels",
    "generate_trials",
    "generate_trials_optuna",
    "has_any_provider_enabled",
    "has_compatible_provider_family",
    "is_valid_provider_trial",
    "refine_trials_around",
    "run_optimization",
    "select_best",
    "space_requires_family_filter",
    "split_holdout",
    "split_train_test",
]
