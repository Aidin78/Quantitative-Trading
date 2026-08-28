# Provider Edge Scorecard — Higher-Timeframe Experiment Plan

**Date:** 2026-08-25 (updated 2026-08-28 — §10 added: full-history confirmation)
**Status:** **CLOSED — classic TA rejected on every timeframe.** The §9 "robust ADX 1d edge" was a ~18-month artifact: on the full 2017–2026 BTC *and* ETH 1d history (§10) it is **0 keep, uniformly negative train** on both symbols. No classic-TA lead remains; next step is a different hypothesis class (§7 item 3), not another parameter grid.
**Baseline rejected:** BTC/USDT **1h** classic TA scorecard — **0 keep / 3 watch / 12 drop**, empty `keep_shortlist`
**Artifacts:** `backend/data/provider_edge_scorecard.json` (1h), this plan, `backend/data/provider_edge_scorecard_4h.json` / `_1d.json` (run output), `backend/data/adx_1d_param_sweep_result.json` (§9 sweep, 18-month), `backend/data/adx_1d_param_sweep_btc_fullhist.json` / `_eth_fullhist.json` (§10 full-history confirmation)

---

## 1. Why 1h is already rejected as baseline

After critical platform bugs were fixed (EMA/MACD/BB confidence calibration, true EMA crossover events, `next_open_v1` fill, daily drawdown), the full provider edge scorecard on **BTC/USDT 1h** still shows **no promoteable edge**:

| Verdict | Count | Configs (1h) |
|---------|------:|--------------|
| keep | 0 | — |
| watch | 3 | `solo_RSI_agree1`, `solo_BB_agree1`, `B_BB_only_agree1` |
| drop | 12 | all other solos, EMA/BB combos, trend/reversion families, fee-halved C |

**Interpretation:** Holdout-positive watch rows (RSI/BB) failed train profitability / sample thresholds — not a stable edge. Empty `keep_shortlist` means discovery must not promote any solo provider from 1h. Next falsifiable step is the same scorecard on **higher timeframes**, where classic TA noise is lower and trade counts remain interpretable on 4h.

---

## 2. Tooling (reuse — do not invent a new framework)

| Piece | Path / command |
|-------|----------------|
| Core logic | `backend/src/validation/provider_edge_scorecard.py` |
| CLI | `backend/scripts/provider_edge_diagnostic.py` |
| Fill default | `config/settings.yaml` → `fill_models.default: next_open_v1` (5 bps slip + 10 bps fee, `fill_at: next_open`) |
| Listed TFs | `config/settings.yaml` → `timeframes: [1h, 4h]` (**1d not listed**; exchange download still accepts `1d` via CLI `--timeframe`) |
| Data | `source=exchange` → Binance via `market_cache.get_or_download_csv` (cached under `backend/data/cache/` / `data/cache/`) |

### Exact CLI (match 1h windows)

```powershell
cd backend

# 4h — required (same calendar window as 1h scorecard JSON)
poetry run python scripts/provider_edge_diagnostic.py `
  --start 2025-01-01 --end 2026-07-18 `
  --symbol "BTC/USDT" --timeframe 4h --mode full `
  --out data/provider_edge_scorecard_4h.json

# 1d — optional if download succeeds and bars are sufficient
poetry run python scripts/provider_edge_diagnostic.py `
  --start 2025-01-01 --end 2026-07-18 `
  --symbol "BTC/USDT" --timeframe 1d --mode full `
  --out data/provider_edge_scorecard_1d.json

# ETH — optional / easy parallel (same params)
poetry run python scripts/provider_edge_diagnostic.py `
  --start 2025-01-01 --end 2026-07-18 `
  --symbol "ETH/USDT" --timeframe 4h --mode full `
  --out data/provider_edge_scorecard_4h_eth.json
```

`--mode full` reuses fixed `BASE_PARAMS` + `FULL_CONFIGS` (8 solos + Pass2 A–D + trend/reversion families + fee-halved sensitivity on `C_EMA_BB_agree1`).

### Reduced subset (only if full run is too heavy)

If wall-clock is prohibitive, run the **meaningful subset** still via the same CLI by temporarily restricting configs, or document a manual pass2 + solos of interest. Preferred reduced set:

1. All **8 solos** (`solo_*_agree1`)
2. Best 1h **watch** configs: `solo_RSI_agree1`, `solo_BB_agree1`, `B_BB_only_agree1` (BB already covered by solo)
3. Optionally `reversion_BB_RSI_agree1` and `C_EMA_BB_agree1`

Rationale: solos drive `keep_shortlist`; RSI/BB were the only non-drop on 1h. Document any reduction in the result JSON notes / this file’s run log.

---

## 3. Fixed experiment parameters

| Knob | Value | Notes |
|------|-------|-------|
| Symbol (primary) | `BTC/USDT` | ETH optional |
| Timeframe | **4h** required; **1d** if data + feasibility | 1d not in `settings.yaml` list — still runnable via CLI |
| Calendar window | `2025-01-01` → `2026-07-18` | Identical to 1h scorecard |
| Window split | holdout 20% of full span; train 70% of remaining (opt) | Same as `split_scorecard_windows` |
| Expected windows (same as 1h JSON) | train ≈ 2025-01-01 → 2025-11-12; test → 2026-03-27; holdout → 2026-07-18 | Chronological, non-overlapping |
| Fill model | **`next_open_v1`** | Default in settings; no look-ahead close fills |
| Engine / providers | `BASE_PARAMS` in scorecard module | `min_confidence=0.65`, SL/TP ATR 1.5/3.0, `max_bars_in_trade=24`, etc. |
| Fee sensitivity | On (default) | Extra row `C_EMA_BB_agree1_fees_halved` |

---

## 4. Pass / fail / keep–watch–drop criteria

**Do not invent new thresholds.** Use `verdict_for_windows()` exactly:

```text
keep  := train_return  >= 0  AND train_trades  >= 20
         AND holdout_return >= 0  AND holdout_trades >= 10

watch := holdout_return >= 0  AND holdout_trades >= 10
         AND train_return < 0

drop  := otherwise
```

Additional promotion gate used by the scorecard payload:

- **`keep_shortlist`**: only **solo** configs with verdict `keep` contribute enabled provider keys.
- Family / Pass2 `keep` is informative but does **not** populate the shortlist alone.
- **Promote to discovery / candidate work:** non-empty `keep_shortlist` on 4h (or 1d) under `next_open_v1`.
- **Fail / abandon classic TA on this TF:** all drop, or only watch with weak holdout and no keep.

Test window is reported for diagnostics but **does not** enter the keep/watch/drop rule.

---

## 5. Decision tree after the run

1. **Any solo `keep` on 4h** → freeze that shortlist; run provider discovery / light Optuna on those enables only; then candidate evaluator.
2. **Only `watch` (esp. RSI/BB again)** → treat as weak signal: one bounded param tune on watch providers **or** reversion family; do **not** promote to live.
3. **All `drop` on 4h** → classic TA on BTC/USDT at 1h–4h is not an edge under this fill/fee model. Next hypotheses (pick 1–2, not all):
   - Extend to **1d** (accept low trade count; still require holdout ≥ 10 trades for keep).
   - Change **hypothesis class** (regime filter / volatility targeting / non-TA feature), not another EMA period sweep.
   - Multi-symbol confirmation (ETH 4h) only if BTC shows watch/keep — do not fish for ETH alone.
4. **1d infeasible** (download fail, or holdout trades << 10 across configs) → document and stop; do not lower trade floors to manufacture “keep”.

---

## 6. Run log (executed 2026-08-25)

| Run | Symbol | TF | Mode | Out file | Outcome |
|-----|--------|----|------|----------|---------|
| Done | BTC/USDT | 4h | **full** (~8 min) | `backend/data/provider_edge_scorecard_4h.json` | **0 keep / 2 watch / 13 drop**; empty shortlist |
| Done | BTC/USDT | 1d | **full** (~1.2 min) | `backend/data/provider_edge_scorecard_1d.json` | **2 keep / 2 watch / 11 drop**; shortlist `adx_enabled` |
| Skipped | ETH/USDT | 4h | — | — | Not run (BTC 4h already failed; ETH deferred) |

**Data:** Binance cache — `data/cache/binance_BTC-USDT_4h.csv` (3379 bars), `…_1d.csv` (564 bars), window `2025-01-01`→`2026-07-18` (same splits as 1h).
**Fill:** `next_open_v1` (settings default). **1d** is not listed in `settings.yaml` `timeframes` but downloads/runs fine via CLI.

### 4h vs 1h (verdict table)

| Config | 1h | 4h | Notes |
|--------|----|----|-------|
| solo_EMA | drop | drop | Near-zero trades on 4h |
| solo_RSI | **watch** | drop | Holdout trades 0 on 4h |
| solo_MACD | drop (0 trades) | drop | Negative all windows 4h |
| solo_ADX | drop | **watch** | Holdout +0.54% / 17 trades; train still red |
| solo_BB | **watch** | drop | Holdout 1 trade / red |
| solo_ST | drop | drop | |
| solo_VOL | drop | drop | 4h: train+holdout both green but train n=14 (<20) → not keep/watch |
| solo_MS | drop | **watch** | Holdout +3.13% / 28; train n=5 red |
| B_BB_only | **watch** | drop | Same as solo BB |
| Pass2 / families | drop | drop | |
| **keep_shortlist** | `[]` | `[]` | No promote on 4h |

**4h verdict:** Classic TA still **fails** as an edge on BTC/USDT 4h under `next_open_v1`. RSI/BB 1h watches did **not** improve; ADX/MS flipped to watch only (no keep).

### 1d summary (feasible; treat cautiously)

| Config | Verdict | Train ret / n | Holdout ret / n |
|--------|---------|---------------|-----------------|
| solo_ADX_agree1 | **keep** | +6.19% / 21 | +0.45% / 16 |
| trend_EMA_MACD_ADX_agree1 | **keep** (family) | +5.29% / 22 | +3.85% / 15 |
| solo_MACD_agree1 | watch | −0.35% / 15 | +2.77% / 11 |
| solo_ST_agree1 | watch | −7.28% / 12 | +0.20% / 18 |
| most EMA/RSI/BB/reversion | drop | 0 trades | — |

`keep_shortlist` = `["adx_enabled"]`. Caveats: samples barely clear floors (train≥20, holdout≥10); ADX **test** window is slightly negative (−0.25%); many providers silent on 1d with fixed params; do **not** promote to live without longer history / ETH confirm / candidate gate.

---

## 7. Recommended next actions (given 4h fail)

1. **Do not** keep fishing EMA/RSI/BB on 1h or 4h — rejected under current fill/fee model.
2. **Bounded follow-up on 1d ADX only:** longer calendar (e.g. 2023→now), ETH/USDT 1d scorecard, then light Optuna on `adx_*` params only if shortlist still holds — feed candidate evaluator (no live).
3. If 1d ADX fails the expanded check: **change hypothesis class** (regime/vol targeting / non-classic-TA features), not another period grid on the same providers.

---

## 9. ADX parameter sensitivity sweep (executed 2026-08-25) — real edge, not a lucky default

**Blocker:** network access to download a longer BTC history or ETH/USDT data was unavailable in this environment (tested directly — `get_or_download_csv` for a wider range hung indefinitely with no error). Item 2's "longer calendar" and "ETH confirm" steps could not be run. What *was* run instead, fully within the existing cache (BTC/USDT 1d, 2025-01-01→2026-07-18, 565 bars, same train/test/holdout split as the original scorecard): a bounded grid sweep of `adx_period` (10, 14), `min_adx` (20, 25, 30), `min_di_spread` (3, 5, 8) — 18 combinations, each a **real** `ValidationHarness`/`DecisionEngine` backtest via `evaluate_params_scorecard` (not a research approximation). Tool: `backend/scripts/run_adx_1d_param_sweep.py`; raw result: `backend/data/adx_1d_param_sweep_result.json`. (`adx_period=20` was attempted but raised `InsufficientDataError` — 565 bars is too short for a 40-bar ADX warmup on top of the smallest train window; only 10 and 14 were completed.)

### Result: `adx_period=10` is robust across the whole neighborhood; `adx_period=14` (the original default) is not

| `adx_period` | keep rate | test window positive | holdout window positive |
|---|---|---|---|
| **10** | 7/9 (78%) | **9/9 (100%)** | **9/9 (100%)** |
| 14 (original default) | 3/9 (33%) | 0/9 (0%) | 3/9 (33%) |

With `adx_period=10`, **every one of the 9 `min_adx`×`min_di_spread` combinations** had positive test *and* holdout return, profit factor > 1 (1.12–2.11 across windows), and positive Sharpe (mostly 1.4–4.5) — the kind of parameter-neighborhood stability none of the trend-following signals in `candidate-stability-findings.md` ever showed (there, a one-notch parameter change routinely flipped the verdict). With `adx_period=14`, the *only* combination that "keeps" is the exact original default (`min_adx=25`); `min_adx=20` makes test catastrophically negative (5 trades, `sharpe=-517`), and `min_adx=30` makes both test and holdout negative despite a much higher train return (+12.46%) — the classic overfit signature (train return *increases* while out-of-sample return *decreases*).

Representative `adx_period=10` row (`min_adx=20, min_di_spread=3`):

| window | return | trades | profit factor | sharpe | max DD |
|---|---|---|---|---|---|
| train | +2.14% | 25 | 1.26 | 1.43 | 5.09% |
| test | +4.41% | 21 | 1.62 | 3.18 | 6.21% |
| holdout | +2.71% | 14 | 1.50 | 2.55 | 2.12% |

### Why this differs from every prior rejected hypothesis

ADX is structurally different from every signal tested in `candidate-stability-findings.md` (EMA, SuperTrend, ADX-*directional*, market structure, order-flow): those all pick a **side** every bar (or nearly every bar) and lose money to whipsaw when the market chops against the trend. `AdxTrendStrengthProvider` only trades when `ADX >= min_adx` *and* `|+DI - -DI| >= min_di_spread` — i.e. it is a **trend-strength gate**, not a directional predictor; most bars it emits nothing. That is very likely why widening the horizon to 1d (fewer, higher-conviction trades) and a shorter ADX lookback (10 vs 14 — more responsive to the strong-trend windows this 18-month BTC period actually had) produced a result that survives a full parameter neighborhood, not just one lucky point.

### Caveats — this is not yet a promotion-ready finding

- **Sample size is still small** (14–27 trades per window) — well above the scorecard's `keep` floor (train≥20, holdout≥10) for most rows, but nowhere close to the "> 100 trades" comfort level `docs/backend/backtesting.md` recommends for outcome metrics.
- **No longer-history or ETH/USDT confirmation was possible** in this environment — the original plan's two confirmation steps remain undone, not because they were tried and failed, but because the network was unavailable. This is a **documented gap, not a negative result** — do not read "network unavailable" as "hypothesis rejected."
- **`adx_period=10` is a *neighbor* of the platform default (14), not something invented from scratch** — `TRIAL_PARAM_KEYS`/`OptimizationSpace` already includes `adx_period` as a tunable, so this is squarely inside the existing optimization surface, not a new parameter.

### Verdict on plan item 7.2

**Partially executed, and the part that could run produced the strongest, most parameter-robust finding of the entire investigation.** Per the plan's own decision tree (§5.1): *"Any solo `keep` on 4h/1d → freeze that shortlist; run provider discovery / light Optuna on those enables only; then candidate evaluator."* `adx_period=10` should be the next input to that step — but **only after** the still-missing confirmation (longer history and/or ETH/USDT) becomes feasible, since a single-symbol, ~18-month, sub-30-trade result is exactly the shape of finding this whole investigation has repeatedly shown can look robust and still not generalize.

> **Update 2026-08-28:** the confirmation ran (§10) and the finding was **rejected**. Do not use `adx_period=10` as an input to §5.1.

---

## 10. Full-history confirmation of the §9 ADX 1d finding — REJECTED (executed 2026-08-28)

Network access was restored. Downloaded the full Binance 1d history for **BTC/USDT and ETH/USDT** (2017-08-17 → 2026-08-27, 3298 bars each, vs the 565 bars §9 had) via `market_cache.download_csv(force=True)` — the overlapping 2025-01→2026-07 range came back byte-identical to the old cache, so the §9 numbers remain reproducible; this only *extends* the window. Re-ran the exact §9 sweep (`run_adx_1d_param_sweep.py`, same `evaluate_params_scorecard` / `split_scorecard_windows` / `verdict_for_windows`) on the full range.

Over 9 years the scorecard split is roughly: train 2017-08 → 2023-01, test 2023-01 → 2025-05, holdout 2025-05 → 2026-08 (the holdout ≈ the window §9 lived in).

### Result: 0 keep on both symbols; every combo has a negative train return

| symbol | `adx_period` | §9 (18-month) | full history (9-year) |
|---|---|---|---|
| BTC/USDT | 10 | 7/9 keep, 9/9 test+holdout positive | **0/9 keep** — train −1.1% to −10.5% on *every* combo |
| BTC/USDT | 14 | 1/9 keep | 0/9 keep |
| ETH/USDT | 10 | (not run in §9) | **0/9 keep** — train −3.0% to −7.8% on every combo |
| ETH/USDT | 14 | (not run in §9) | 0/9 keep |

BTC full-history summary: **0 keep / 8 watch / 10 drop / 9 error** (the 9 errors are all `adx_period=20` — see infra note below). ETH: **0 keep / 13 watch / 5 drop**.

Every `watch` verdict is an artifact, not an edge:
- **BTC** `watch` rows (`adx_period` 10 & 14, `min_adx=30`): train ≈ −6.9% on only **6–7 trades**, holdout barely positive (+0.3% to +1.2%). The `p=14 min_adx=30` rows show holdout +8% / 47–49 trades — but on 7 train trades that is one lucky holdout regime, and `verdict_for_windows` correctly refuses it `keep` because train is deeply negative.
- **ETH** `watch` rows: holdout returns of +13% to **+29%** — but train −6.5% on **5–7 trades** and test *also* negative in all 13. ETH's 2025-05→2026-08 holdout had a strong directional run that any trend-strength gate rode; with a near-empty, negative train window that is noise, not signal.

### Why the §9 result looked robust and was not

§9's "full parameter neighborhood is positive" was measured entirely inside a single 18-month window (2025-01 → 2026-07) that, in hindsight, was one favorable BTC trend regime sliced three ways. A shorter ADX lookback (10) is *more* responsive to exactly that kind of sustained-trend window — which is why the whole `min_adx`×`min_di_spread` grid moved together and looked stable. Extend the train window to include 2018, 2019, the 2021 double-top, and the 2022 bear, and the gate has no edge in any of them: solo-ADX on 1d is a **trend-strength filter with no directional or timing edge across regimes**, and the fee/slippage drag (`candidate-stability-findings.md` — ~0.3% round trip) does the rest.

### Structural dead-end, independent of the edge question

Even with 3298 bars, solo-ADX on 1d produces only **6–33 trades per multi-year window** (`min_confidence=0.65`, `max_bars_in_trade=24`, gate rarely open). It can never reach the ">100 trades" bar `docs/backend/backtesting.md` wants for trustworthy outcome metrics. 1d + a single gated provider is structurally trade-starved regardless of parameters.

### Infra note (not blocking, worth fixing separately)

`ValidationHarness.run` computes its warm-up skip via `compute_min_lookback_bars()` with **no argument**, so it reads `config/features.yaml` from disk (`adx_period=14` → skip 29) and ignores the trial's `features_config` override. Any trial with `adx_period=20` (needs `2*period = 40` bars) therefore raises `InsufficientDataError` on the first cycle regardless of how much data is loaded. The sweep script now records these as `verdict:"error"` instead of aborting. Real fix: pass the runtime's actual `FeatureBuilder.config` into the lookback calc (`compute_min_lookback_bars` already takes an optional arg; it just needs a `FeaturesConfig` overload and a call-site change in `harness.py:106`).

### Verdict

**The §9 ADX 1d edge is rejected.** Combined with the 1h (0 keep) and 4h (0 keep) scorecards and the entire `candidate-stability-findings.md` investigation, **classic TA on BTC/USDT (and ETH/USDT) across 1h/4h/1d is exhausted as an edge source under the real `next_open_v1` fill/fee model.** Per the §5 decision tree (item 3) and §7 (item 3), the only remaining move is to **change the hypothesis class** — regime detection / volatility targeting / a non-TA feature (funding, basis, on-chain, cross-asset) — not another period grid on the same providers.

---

## 8. Non-goals

- No live order execution.
- No new scorecard framework.
- No inventing profitable results; report real metrics only.
- No git commit unless explicitly requested.
