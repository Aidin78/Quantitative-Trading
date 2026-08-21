from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
from typing import Any

TRIAL_PARAM_KEYS = [
    "min_confidence",
    "min_risk_reward",
    "min_agreeing_providers",
    "sl_atr_mult",
    "tp_atr_mult",
    "max_bars_in_trade",
    "oversold",
    "overbought",
    "risk_pct_per_trade",
    "min_atr_pct",
    "session_preset",
    "max_signals_per_day",
    "ema_fast",
    "ema_slow",
    "rsi_period",
    "ema_weight",
    "rsi_weight",
    "ema_enabled",
    "rsi_enabled",
    "macd_fast",
    "macd_slow",
    "macd_signal_period",
    "macd_weight",
    "macd_enabled",
    "require_signal_align",
    "min_histogram_slope",
    "adx_period",
    "adx_weight",
    "adx_enabled",
    "min_adx",
    "min_di_spread",
    "adx_require_trend",
    "bb_period",
    "bb_std",
    "bb_weight",
    "bb_enabled",
    "bb_avoid_high_vol",
    "bb_max_adx",
    "st_period",
    "st_multiplier",
    "st_weight",
    "st_enabled",
    "st_require_trend",
    "vol_period",
    "vol_weight",
    "vol_enabled",
    "min_cmf",
    "min_volume_ratio",
    "vol_require_price_align",
    "ms_pivot_bars",
    "ms_weight",
    "ms_enabled",
    "ms_require_bos",
    "ms_require_trend",
]

PROVIDER_ENABLED_KEYS = (
    "ema_enabled",
    "rsi_enabled",
    "macd_enabled",
    "adx_enabled",
    "bb_enabled",
    "st_enabled",
    "vol_enabled",
    "ms_enabled",
)

TREND_FAMILY_KEYS = (
    "ema_enabled",
    "macd_enabled",
    "adx_enabled",
    "st_enabled",
    "ms_enabled",
)
REVERSION_FAMILY_KEYS = (
    "bb_enabled",
    "rsi_enabled",
)


def has_any_provider_enabled(params: dict[str, Any]) -> bool:
    return any(int(params.get(key, 0)) for key in PROVIDER_ENABLED_KEYS)


def has_compatible_provider_family(params: dict[str, Any]) -> bool:
    """Reject combos that mix trend and mean-reversion paradigms (VOL may join either)."""
    has_trend = any(int(params.get(key, 0)) for key in TREND_FAMILY_KEYS)
    has_reversion = any(int(params.get(key, 0)) for key in REVERSION_FAMILY_KEYS)
    return not (has_trend and has_reversion)


def is_valid_provider_trial(
    params: dict[str, Any],
    *,
    require_compatible_family: bool = False,
) -> bool:
    if not has_any_provider_enabled(params):
        return False
    if require_compatible_family and not has_compatible_provider_family(params):
        return False
    return True


def space_requires_family_filter(space: OptimizationSpace) -> bool:
    """Discovery-like spaces toggle multiple providers; enforce paradigm separation."""
    togglable = sum(1 for key in PROVIDER_ENABLED_KEYS if len(getattr(space, key)) > 1)
    return togglable >= 2


@dataclass(frozen=True)
class OptimizationSpace:
    min_confidence: tuple[float, ...] = (0.6, 0.65, 0.7, 0.78)
    min_risk_reward: tuple[float, ...] = (1.0, 1.2, 1.5, 2.0)
    min_agreeing_providers: tuple[int, ...] = (1, 2)
    sl_atr_mult: tuple[float, ...] = (1.0, 1.5, 2.0)
    tp_atr_mult: tuple[float, ...] = (2.0, 3.0, 4.0)
    max_bars_in_trade: tuple[int, ...] = (12, 24, 48)
    oversold: tuple[float, ...] = (25.0, 30.0, 35.0)
    overbought: tuple[float, ...] = (65.0, 70.0, 75.0)
    risk_pct_per_trade: tuple[float, ...] = (0.5, 1.0, 1.5)
    min_atr_pct: tuple[float, ...] = (0.1, 0.3, 0.5)
    session_preset: tuple[str, ...] = ("eu_us", "all")
    max_signals_per_day: tuple[int, ...] = (5, 10, 20)
    ema_fast: tuple[int, ...] = (12,)
    ema_slow: tuple[int, ...] = (26,)
    rsi_period: tuple[int, ...] = (14,)
    ema_weight: tuple[float, ...] = (1.0,)
    rsi_weight: tuple[float, ...] = (1.0,)
    ema_enabled: tuple[int, ...] = (1,)
    rsi_enabled: tuple[int, ...] = (1,)
    macd_fast: tuple[int, ...] = (12,)
    macd_slow: tuple[int, ...] = (26,)
    macd_signal_period: tuple[int, ...] = (9,)
    macd_weight: tuple[float, ...] = (1.0,)
    macd_enabled: tuple[int, ...] = (1,)
    require_signal_align: tuple[int, ...] = (1,)
    min_histogram_slope: tuple[float, ...] = (0.0,)
    adx_period: tuple[int, ...] = (14,)
    adx_weight: tuple[float, ...] = (1.0,)
    adx_enabled: tuple[int, ...] = (0,)
    min_adx: tuple[float, ...] = (25.0,)
    min_di_spread: tuple[float, ...] = (5.0,)
    adx_require_trend: tuple[int, ...] = (0,)
    bb_period: tuple[int, ...] = (20,)
    bb_std: tuple[float, ...] = (2.0,)
    bb_weight: tuple[float, ...] = (1.0,)
    bb_enabled: tuple[int, ...] = (0,)
    bb_avoid_high_vol: tuple[int, ...] = (1,)
    bb_max_adx: tuple[float, ...] = (0.0,)
    st_period: tuple[int, ...] = (10,)
    st_multiplier: tuple[float, ...] = (3.0,)
    st_weight: tuple[float, ...] = (1.0,)
    st_enabled: tuple[int, ...] = (0,)
    st_require_trend: tuple[int, ...] = (0,)
    vol_period: tuple[int, ...] = (20,)
    vol_weight: tuple[float, ...] = (1.0,)
    vol_enabled: tuple[int, ...] = (0,)
    min_cmf: tuple[float, ...] = (0.05,)
    min_volume_ratio: tuple[float, ...] = (1.2,)
    vol_require_price_align: tuple[int, ...] = (1,)
    ms_pivot_bars: tuple[int, ...] = (5,)
    ms_weight: tuple[float, ...] = (1.0,)
    ms_enabled: tuple[int, ...] = (0,)
    ms_require_bos: tuple[int, ...] = (1,)
    ms_require_trend: tuple[int, ...] = (0,)

    def as_dict(self) -> dict[str, tuple[Any, ...]]:
        return {key: getattr(self, key) for key in TRIAL_PARAM_KEYS}

    @classmethod
    def from_dict(cls, data: dict[str, list[Any]] | None) -> OptimizationSpace:
        if not data:
            return cls()
        fields: dict[str, tuple[Any, ...]] = {}
        defaults = cls()
        for key in TRIAL_PARAM_KEYS:
            if key in data:
                fields[key] = tuple(data[key])
            else:
                fields[key] = getattr(defaults, key)
        return cls(**fields)

    @classmethod
    def provider_discovery(cls) -> OptimizationSpace:
        """Search space: each provider on/off, other params fixed."""
        return cls.from_dict(PROVIDER_DISCOVERY_SPACE)

    @classmethod
    def provider_discovery_constrained(
        cls,
        *,
        keep_shortlist: list[str] | None = None,
    ) -> OptimizationSpace:
        """Family-aware discovery: agree in {1,2}; optional scorecard shortlist freeze."""
        space = dict(PROVIDER_DISCOVERY_CONSTRAINED_SPACE)
        if keep_shortlist:
            keep = {key for key in keep_shortlist if key in PROVIDER_ENABLED_KEYS}
            if keep:
                for key in PROVIDER_ENABLED_KEYS:
                    space[key] = [0, 1] if key in keep else [0]
        return cls.from_dict(space)

    @classmethod
    def bb_solo_tuning(cls) -> OptimizationSpace:
        """BB-only threshold/exit search; all other providers fixed off."""
        return cls.from_dict(BB_SOLO_TUNING_SPACE)


PROVIDER_DISCOVERY_SPACE: dict[str, list[Any]] = {
    "min_confidence": [0.65],
    "min_risk_reward": [1.2],
    "min_agreeing_providers": [1, 2, 3],
    "sl_atr_mult": [1.5],
    "tp_atr_mult": [3.0],
    "max_bars_in_trade": [24],
    "oversold": [30],
    "overbought": [70],
    "risk_pct_per_trade": [1.0],
    "min_atr_pct": [0.3],
    "session_preset": ["all"],
    "max_signals_per_day": [10],
    "ema_fast": [12],
    "ema_slow": [26],
    "rsi_period": [14],
    "ema_weight": [1.0],
    "rsi_weight": [1.0],
    "ema_enabled": [0, 1],
    "rsi_enabled": [0, 1],
    "macd_fast": [12],
    "macd_slow": [26],
    "macd_signal_period": [9],
    "macd_weight": [1.0],
    "macd_enabled": [0, 1],
    "require_signal_align": [1],
    "min_histogram_slope": [0.0],
    "adx_period": [14],
    "adx_weight": [1.0],
    "adx_enabled": [0, 1],
    "min_adx": [25],
    "min_di_spread": [5],
    "adx_require_trend": [0],
    "bb_period": [20],
    "bb_std": [2.0],
    "bb_weight": [1.0],
    "bb_enabled": [0, 1],
    "bb_avoid_high_vol": [1],
    "bb_max_adx": [0],
    "st_period": [10],
    "st_multiplier": [3.0],
    "st_weight": [1.0],
    "st_enabled": [0, 1],
    "st_require_trend": [0],
    "vol_period": [20],
    "vol_weight": [1.0],
    "vol_enabled": [0, 1],
    "min_cmf": [0.05],
    "min_volume_ratio": [1.2],
    "vol_require_price_align": [1],
    "ms_pivot_bars": [5],
    "ms_weight": [1.0],
    "ms_enabled": [0, 1],
    "ms_require_bos": [1],
    "ms_require_trend": [0],
}

# Constrained discovery: drop agree=3; family filter applied at trial generation.
PROVIDER_DISCOVERY_CONSTRAINED_SPACE: dict[str, list[Any]] = {
    **PROVIDER_DISCOVERY_SPACE,
    "min_agreeing_providers": [1, 2],
}

# Bollinger solo: tune bands / filters / exits; no provider on/off search.
BB_SOLO_TUNING_SPACE: dict[str, list[Any]] = {
    **PROVIDER_DISCOVERY_SPACE,
    "min_confidence": [0.55, 0.6, 0.65, 0.7, 0.78],
    "min_agreeing_providers": [1],
    "sl_atr_mult": [1.0, 1.5, 2.0],
    "tp_atr_mult": [2.0, 3.0, 4.0],
    "max_bars_in_trade": [12, 24, 48],
    "min_atr_pct": [0.1, 0.3, 0.5],
    "ema_enabled": [0],
    "rsi_enabled": [0],
    "macd_enabled": [0],
    "adx_enabled": [0],
    "bb_enabled": [1],
    "bb_period": [14, 20, 26],
    "bb_std": [1.5, 2.0, 2.5],
    "bb_avoid_high_vol": [0, 1],
    "bb_max_adx": [0, 20, 25, 30],
    "st_enabled": [0],
    "vol_enabled": [0],
    "ms_enabled": [0],
}


_PROVIDER_CHIP_LABELS = {
    "ema_enabled": "EMA",
    "rsi_enabled": "RSI",
    "macd_enabled": "MACD",
    "adx_enabled": "ADX",
    "bb_enabled": "BB",
    "st_enabled": "ST",
    "vol_enabled": "VOL",
    "ms_enabled": "MS",
}


def enabled_provider_labels(params: dict[str, Any]) -> list[str]:
    return [label for key, label in _PROVIDER_CHIP_LABELS.items() if int(params.get(key, 0)) == 1]


def generate_trials(
    space: OptimizationSpace,
    *,
    max_trials: int = 40,
    seed: int | None = None,
    require_compatible_family: bool | None = None,
) -> list[dict[str, Any]]:
    enforce_family = (
        space_requires_family_filter(space)
        if require_compatible_family is None
        else require_compatible_family
    )
    values = [space.as_dict()[key] for key in TRIAL_PARAM_KEYS]
    all_combos = [
        dict(zip(TRIAL_PARAM_KEYS, combo, strict=True)) for combo in itertools.product(*values)
    ]
    all_combos = [
        combo
        for combo in all_combos
        if is_valid_provider_trial(combo, require_compatible_family=enforce_family)
    ]
    if not all_combos:
        raise ValueError("Optimization space has no valid provider combinations")
    if len(all_combos) <= max_trials:
        return all_combos

    rng = random.Random(seed if seed is not None else random.randrange(2**31))
    stride = max(1, len(all_combos) // max_trials)
    picked: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    for index in range(0, len(all_combos), stride):
        combo = all_combos[index]
        key = tuple(sorted(combo.items()))
        if key not in seen:
            seen.add(key)
            picked.append(combo)
        if len(picked) >= max_trials:
            break

    remaining = [combo for combo in all_combos if tuple(sorted(combo.items())) not in seen]
    while len(picked) < max_trials and remaining:
        choice = rng.choice(remaining)
        key = tuple(sorted(choice.items()))
        if key in seen:
            remaining.remove(choice)
            continue
        seen.add(key)
        picked.append(choice)
        remaining.remove(choice)
    return picked


def _suggest_params_from_optuna_trial(
    trial: Any,
    space: OptimizationSpace,
) -> dict[str, Any]:
    space_map = space.as_dict()
    params: dict[str, Any] = {}
    for key in TRIAL_PARAM_KEYS:
        values = list(space_map[key])
        if len(values) == 1:
            params[key] = values[0]
        else:
            params[key] = trial.suggest_categorical(key, values)
    return params


def _make_optuna_study(seed: int | None):
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = (
        optuna.samplers.TPESampler(seed=seed) if seed is not None else optuna.samplers.TPESampler()
    )
    return optuna.create_study(direction="maximize", sampler=sampler)


def generate_trials_optuna(
    space: OptimizationSpace,
    *,
    max_trials: int = 40,
    seed: int | None = None,
    require_compatible_family: bool | None = None,
) -> list[dict[str, Any]]:
    """Ask Optuna for ``max_trials`` distinct parameter sets without ever
    scoring them, so the TPE sampler never receives feedback and effectively
    degenerates to sampling from its prior. This is intentional here: callers
    that batch/parallelize trial execution (max_parallel_trials > 1) can't
    interleave tell() between asks anyway. For adaptive sequential search,
    use run_optuna_trials instead, which does ask -> evaluate -> tell per
    trial.
    """
    enforce_family = (
        space_requires_family_filter(space)
        if require_compatible_family is None
        else require_compatible_family
    )
    study = _make_optuna_study(seed)
    picked: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    max_attempts = max(max_trials * 20, max_trials)
    attempts = 0
    while len(picked) < max_trials and attempts < max_attempts:
        attempts += 1
        trial = study.ask()
        params = _suggest_params_from_optuna_trial(trial, space)
        if not is_valid_provider_trial(params, require_compatible_family=enforce_family):
            continue
        key = tuple(sorted(params.items()))
        if key in seen:
            continue
        seen.add(key)
        picked.append(params)
    return picked


async def run_optuna_trials(
    space: OptimizationSpace,
    evaluate: Any,
    *,
    max_trials: int = 40,
    seed: int | None = None,
    require_compatible_family: bool | None = None,
    study: Any | None = None,
) -> list[Any]:
    """Adaptive sequential search: ask Optuna for one trial, score it with
    ``evaluate`` (an async callable taking the trial's params dict and
    returning a float score), then tell Optuna the result before asking for
    the next one. Unlike generate_trials_optuna, this is genuine Bayesian
    optimization -- each trial's sampling is informed by every prior result.

    ``study`` can be supplied to inspect the sampler's state after the run
    (tests) or to reuse a study across calls; a fresh one is created if
    omitted.

    Returns the list of values evaluate() returned, in trial order, so
    callers can build their own result objects from the scores.
    """
    import optuna

    enforce_family = (
        space_requires_family_filter(space)
        if require_compatible_family is None
        else require_compatible_family
    )
    study = study if study is not None else _make_optuna_study(seed)
    results: list[Any] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    max_attempts = max(max_trials * 20, max_trials)
    attempts = 0
    while len(results) < max_trials and attempts < max_attempts:
        attempts += 1
        trial = study.ask()
        params = _suggest_params_from_optuna_trial(trial, space)
        if not is_valid_provider_trial(params, require_compatible_family=enforce_family):
            study.tell(trial, state=optuna.trial.TrialState.FAIL)
            continue
        key = tuple(sorted(params.items()))
        if key in seen:
            study.tell(trial, state=optuna.trial.TrialState.FAIL)
            continue
        seen.add(key)
        score, result = await evaluate(params)
        study.tell(trial, score)
        results.append(result)
    return results


def refine_trials_around(
    top_trials: list[dict[str, Any]],
    space: OptimizationSpace,
    *,
    max_refine: int = 9,
) -> list[dict[str, Any]]:
    refine_keys = ("sl_atr_mult", "tp_atr_mult", "oversold", "overbought", "min_atr_pct")
    space_map = space.as_dict()
    refined: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()

    for params in top_trials:
        base_key = tuple(sorted(params.items()))
        seen.add(base_key)
        for key in refine_keys:
            values = list(space_map[key])
            if key not in params or len(values) < 2:
                continue
            current = params[key]
            try:
                idx = values.index(current)
            except ValueError:
                continue
            for neighbor_idx in (idx - 1, idx + 1):
                if 0 <= neighbor_idx < len(values):
                    candidate = dict(params)
                    candidate[key] = values[neighbor_idx]
                    candidate_key = tuple(sorted(candidate.items()))
                    if candidate_key not in seen:
                        seen.add(candidate_key)
                        refined.append(candidate)
                        if len(refined) >= max_refine:
                            return refined
    return refined
