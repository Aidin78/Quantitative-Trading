"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, PlayCircle, ShieldCheck, Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { OptimizationTrialsTable } from "@/components/optimization/OptimizationTrialsTable";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { DateRangeFields } from "@/components/ui/DateRangeFields";
import { FieldLabel } from "@/components/ui/FieldLabel";
import { useActiveOptimizationSweep } from "@/contexts/OptimizationSweepContext";
import { useActiveValidationJob } from "@/contexts/ValidationJobContext";
import { api } from "@/lib/api";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";
import { dateRangeForPreset } from "@/lib/dateRange";
import {
  enabledProviderChips,
  fmtParamsWithoutEnabled,
  spaceForMode,
  type SweepMode,
} from "@/lib/optimizationSpaces";

function fmtParams(params: Record<string, number | string>) {
  return fmtParamsWithoutEnabled(params);
}

const DEFAULT_RANGE = dateRangeForPreset("180d");

export default function OptimizationPage() {
  return (
    <Suspense
      fallback={
        <div className="page-container flex items-center justify-center gap-2 py-24 text-muted">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
          Loading optimization…
        </div>
      }
    >
      <OptimizationPageContent />
    </Suspense>
  );
}

function OptimizationPageContent() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    sweepId,
    setActiveSweepId,
    sweep,
    isActive: isSweepActive,
  } = useActiveOptimizationSweep();
  const { setActiveJobId } = useActiveValidationJob();
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [startDate, setStartDate] = useState(DEFAULT_RANGE.start);
  const [endDate, setEndDate] = useState(DEFAULT_RANGE.end);
  const [initialCapital, setInitialCapital] = useState(10000);
  const [trainRatio, setTrainRatio] = useState(0.7);
  const [maxTrials, setMaxTrials] = useState(60);
  const [topK, setTopK] = useState(5);
  const [minTrades, setMinTrades] = useState(50);
  const [walkForwardWindows, setWalkForwardWindows] = useState(1);
  const [walkForwardMode, setWalkForwardMode] = useState<"fixed" | "anchored">(
    "anchored",
  );
  const [searchMethod, setSearchMethod] = useState<"grid" | "optuna">("optuna");
  const [holdoutRatio, setHoldoutRatio] = useState(0.2);
  const [sweepMode, setSweepMode] = useState<SweepMode>("baseline");

  useEffect(() => {
    const fromUrl = searchParams.get("sweep");
    if (fromUrl) {
      setActiveSweepId(fromUrl);
    }
  }, [searchParams, setActiveSweepId]);

  const persistSweepId = (id: string) => {
    setActiveSweepId(id);
    router.replace(`/optimization?sweep=${encodeURIComponent(id)}`, {
      scroll: false,
    });
  };

  const run = useMutation({
    mutationFn: () =>
      api.runOptimization({
        symbol,
        timeframe: "1h",
        start_date: startDate,
        end_date: endDate,
        source: "exchange",
        initial_capital: initialCapital,
        train_ratio: trainRatio,
        max_trials: maxTrials,
        top_k: topK,
        min_trades: minTrades,
        holdout_ratio: holdoutRatio,
        walk_forward_windows: walkForwardWindows,
        walk_forward_mode: walkForwardMode,
        search_method: searchMethod,
        local_refine: sweepMode === "baseline",
        space: spaceForMode(sweepMode),
      }),
    onSuccess: (res) => persistSweepId(res.id),
  });

  const apply = useMutation({
    mutationFn: (useFallback: boolean) =>
      api.applyOptimization(sweepId!, { use_fallback: useFallback }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["optimization", sweepId] });
    },
  });

  const statusVariant =
    sweep?.status === "completed"
      ? "success"
      : sweep?.status === "failed"
        ? "danger"
        : "accent";

  const progressPct =
    sweep?.progress && sweep.progress.total > 0
      ? Math.round((sweep.progress.current / sweep.progress.total) * 100)
      : 0;

  const topTrialIds = new Set(
    (sweep?.trials ?? [])
      .filter((t) => t.test_score != null)
      .sort(
        (a, b) =>
          (b.composite_score ?? b.test_score ?? 0) -
          (a.composite_score ?? a.test_score ?? 0),
      )
      .slice(0, topK)
      .map((t) => t.trial_id),
  );

  const bestBelowMinTrades =
    sweep?.best_valid === false ||
    (sweep?.best?.test_total_trades != null &&
      sweep.best.test_total_trades < minTrades);

  const displayTrial =
    sweep?.best_valid && sweep.best
      ? sweep.best
      : (sweep?.fallback_trial ?? sweep?.best ?? null);

  const validateHoldout = useMutation({
    mutationFn: async () => {
      if (!sweep?.holdout_start || !sweep.holdout_end || !displayTrial) {
        throw new Error("Holdout period or trial not available");
      }
      return api.runValidation({
        symbol: sweep.symbol ?? symbol,
        timeframe: sweep.timeframe ?? "1h",
        start_date: sweep.holdout_start.slice(0, 10),
        end_date: sweep.holdout_end.slice(0, 10),
        source: "exchange",
        initial_capital: initialCapital,
        revision_id: displayTrial.revision_id ?? undefined,
      });
    },
    onSuccess: (res) => {
      setActiveJobId(res.id);
      router.push(`/validation?job=${encodeURIComponent(res.id)}`);
    },
  });

  return (
    <div className="page-container">
      <PageHeader
        title="Auto Optimizer"
        description="Walk-forward grid search with composite scoring, holdout reserve, and local refinement."
      />

      <Card
        title="Optimization mode"
        subtitle="Choose what the sweep searches"
        className="mb-6"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => {
              setSweepMode("baseline");
              setMaxTrials(60);
              setMinTrades(50);
            }}
            className={`rounded-lg border p-4 text-left transition-colors ${
              sweepMode === "baseline"
                ? "border-accent bg-[var(--accent-dim)]"
                : "border-[var(--border)] hover:border-accent/40"
            }`}
          >
            <p className="font-medium text-foreground">Baseline tuning</p>
            <p className="mt-1 text-sm text-muted">
              EMA + RSI + MACD always on. Tune thresholds, periods, and risk
              params.
            </p>
          </button>
          <button
            type="button"
            onClick={() => {
              setSweepMode("discovery");
              setMaxTrials(40);
              setMinTrades(30);
              setSearchMethod("optuna");
            }}
            className={`rounded-lg border p-4 text-left transition-colors ${
              sweepMode === "discovery"
                ? "border-accent bg-[var(--accent-dim)]"
                : "border-[var(--border)] hover:border-accent/40"
            }`}
          >
            <p className="font-medium text-foreground">Provider discovery</p>
            <p className="mt-1 text-sm text-muted">
              Any of 8 providers on/off + min agreeing providers. Best for
              finding the winning combo.
            </p>
          </button>
        </div>
      </Card>

      <Card
        title={
          sweepMode === "baseline" ? "Baseline workflow" : "Discovery workflow"
        }
        subtitle={
          sweepMode === "baseline"
            ? "Recommended path for EMA + RSI + MACD"
            : "Find the best provider combination"
        }
        className="mb-6"
      >
        {sweepMode === "baseline" ? (
          <ol className="list-decimal space-y-2 pl-5 text-sm text-muted">
            <li>
              Market Data — ingest{" "}
              <strong className="text-foreground">6–12 months</strong> of OHLCV
              for your symbol.
            </li>
            <li>
              Providers — click{" "}
              <strong className="text-foreground">Apply baseline</strong> to
              enable and reset EMA, RSI, and MACD.
            </li>
            <li>
              Run Optimization with the defaults below (180d, Optuna, 60
              trials).
            </li>
            <li>
              Holdout gate — click{" "}
              <strong className="text-foreground">Apply</strong> only if holdout
              passed; otherwise tune or disable one provider.
            </li>
          </ol>
        ) : (
          <ol className="list-decimal space-y-2 pl-5 text-sm text-muted">
            <li>
              Market Data — at least{" "}
              <strong className="text-foreground">180d</strong> OHLCV for your
              symbol.
            </li>
            <li>
              Select{" "}
              <strong className="text-foreground">Provider discovery</strong>{" "}
              above and run 40 Optuna trials (defaults adjust automatically).
              Each trial takes ~2–4 min on 180d data; bar-level progress appears
              while training.
            </li>
            <li>
              Review trials — active providers show as chips (EMA, RSI, ADX, …).
              Pick highest composite score on test data.
            </li>
            <li>
              Apply best config, then validate on holdout before going live.
            </li>
          </ol>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          title="Sweep Configuration"
          subtitle="Train/test split with walk-forward folds"
        >
          <div className="space-y-4">
            <div>
              <FieldLabel label="Symbol" tooltip={FORM_TOOLTIPS.symbol} />
              <input
                className="input-field mt-2"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
              />
            </div>
            <DateRangeFields
              layout="grid"
              startDate={startDate}
              endDate={endDate}
              onStartDateChange={setStartDate}
              onEndDateChange={setEndDate}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <FieldLabel
                  label="Train Ratio"
                  tooltip={FORM_TOOLTIPS.trainRatio}
                />
                <input
                  type="number"
                  min={0.1}
                  max={0.9}
                  step={0.05}
                  className="input-field mt-2"
                  value={trainRatio}
                  onChange={(e) => setTrainRatio(Number(e.target.value))}
                />
              </div>
              <div>
                <FieldLabel
                  label="Initial Capital"
                  tooltip={FORM_TOOLTIPS.initialCapital}
                />
                <input
                  type="number"
                  className="input-field mt-2"
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(Number(e.target.value))}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <FieldLabel
                  label="Max Trials"
                  tooltip={FORM_TOOLTIPS.maxTrials}
                />
                <input
                  type="number"
                  min={1}
                  max={200}
                  className="input-field mt-2"
                  value={maxTrials}
                  onChange={(e) => setMaxTrials(Number(e.target.value))}
                />
              </div>
              <div>
                <FieldLabel label="Top K (test)" tooltip={FORM_TOOLTIPS.topK} />
                <input
                  type="number"
                  min={1}
                  max={20}
                  className="input-field mt-2"
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <FieldLabel
                  label="Min Trades"
                  tooltip={FORM_TOOLTIPS.minTrades}
                />
                <input
                  type="number"
                  min={0}
                  className="input-field mt-2"
                  value={minTrades}
                  onChange={(e) => setMinTrades(Number(e.target.value))}
                />
              </div>
              <div>
                <FieldLabel
                  label="WF Windows"
                  tooltip={FORM_TOOLTIPS.walkForwardWindows}
                />
                <input
                  type="number"
                  min={1}
                  max={6}
                  className="input-field mt-2"
                  value={walkForwardWindows}
                  onChange={(e) =>
                    setWalkForwardWindows(Number(e.target.value))
                  }
                />
              </div>
              <div>
                <FieldLabel
                  label="Holdout Ratio"
                  tooltip={FORM_TOOLTIPS.holdoutRatio}
                />
                <input
                  type="number"
                  min={0}
                  max={0.4}
                  step={0.05}
                  className="input-field mt-2"
                  value={holdoutRatio}
                  onChange={(e) => setHoldoutRatio(Number(e.target.value))}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <FieldLabel
                  label="Search Method"
                  tooltip={FORM_TOOLTIPS.searchMethod}
                />
                <select
                  className="input-field mt-2"
                  value={searchMethod}
                  onChange={(e) =>
                    setSearchMethod(e.target.value as "grid" | "optuna")
                  }
                >
                  <option value="grid">Grid (random sample)</option>
                  <option value="optuna">Optuna (TPE)</option>
                </select>
              </div>
              <div>
                <FieldLabel
                  label="WF Mode"
                  tooltip={FORM_TOOLTIPS.walkForwardMode}
                />
                <select
                  className="input-field mt-2"
                  value={walkForwardMode}
                  onChange={(e) =>
                    setWalkForwardMode(e.target.value as "fixed" | "anchored")
                  }
                  disabled={walkForwardWindows <= 1}
                >
                  <option value="anchored">Anchored</option>
                  <option value="fixed">Fixed rolling</option>
                </select>
              </div>
            </div>
            <p className="text-xs text-muted">
              Last {Math.round(holdoutRatio * 100)}% is reserved as holdout and
              auto-evaluated on the best config after selection.
            </p>
            {run.error && (
              <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                {run.error instanceof Error
                  ? run.error.message
                  : "Optimization failed to start"}
              </p>
            )}
            <button
              type="button"
              onClick={() => run.mutate()}
              disabled={run.isPending || isSweepActive}
              className="btn-primary w-full"
            >
              {run.isPending || isSweepActive ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {isSweepActive ? "Optimization running…" : "Run Optimization"}
            </button>
          </div>
        </Card>

        <Card
          title="Sweep Status"
          subtitle={sweepId ? `ID: ${sweepId}` : "No active sweep"}
        >
          {!sweep ? (
            <EmptyState
              message="No optimization sweep yet"
              hint="Configure and start a sweep"
            />
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant={statusVariant} dot>
                  {sweep.status}
                </Badge>
                {sweep.phase && isSweepActive ? (
                  <Badge
                    variant={
                      sweep.phase === "test"
                        ? "success"
                        : sweep.phase === "refine"
                          ? "accent"
                          : "accent"
                    }
                  >
                    {sweep.phase === "test"
                      ? "Test phase"
                      : sweep.phase === "refine"
                        ? "Refine phase"
                        : "Train phase"}
                  </Badge>
                ) : null}
                {(sweep.status === "pending" || sweep.status === "running") && (
                  <Loader2 className="h-4 w-4 animate-spin text-accent" />
                )}
                {sweep.elapsed_seconds != null ? (
                  <span className="ml-auto text-xs text-muted">
                    {sweep.elapsed_seconds < 60
                      ? `${Math.round(sweep.elapsed_seconds)}s`
                      : `${Math.floor(sweep.elapsed_seconds / 60)}m ${Math.round(
                          sweep.elapsed_seconds % 60,
                        )}s`}
                  </span>
                ) : null}
              </div>

              {isSweepActive ? (
                <p className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/60 p-3 text-sm text-foreground">
                  {sweep.message ||
                    (sweep.status === "pending"
                      ? "Queued — starting sweep…"
                      : "Working…")}
                </p>
              ) : null}

              {sweep.progress && isSweepActive ? (
                <div>
                  <div className="mb-1 flex justify-between text-xs text-muted">
                    <span>Overall progress</span>
                    <span>
                      {sweep.progress.current} / {sweep.progress.total}{" "}
                      backtests ({progressPct}%)
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[var(--border)]">
                    <div
                      className="h-full bg-accent transition-all"
                      style={{ width: `${progressPct}%` }}
                    />
                  </div>
                </div>
              ) : null}

              {sweep.status === "completed" ? (
                <p className="rounded-lg border border-[var(--success)]/20 bg-[var(--success-dim)] p-3 text-sm text-[var(--success)]">
                  Sweep complete. Review composite score and holdout dates
                  below.
                </p>
              ) : null}

              {sweep.error && (
                <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                  {sweep.error}
                </p>
              )}
              {sweep.train_start && sweep.test_end ? (
                <p className="text-xs text-muted">
                  Train: {sweep.train_start.slice(0, 10)} →{" "}
                  {sweep.train_end?.slice(0, 10)} · Test:{" "}
                  {sweep.test_start?.slice(0, 10)} →{" "}
                  {sweep.test_end.slice(0, 10)}
                  {sweep.holdout_start && sweep.holdout_end ? (
                    <>
                      {" "}
                      · Holdout: {sweep.holdout_start.slice(0, 10)} →{" "}
                      {sweep.holdout_end.slice(0, 10)}
                    </>
                  ) : null}
                </p>
              ) : null}
            </div>
          )}
        </Card>
      </div>

      {sweep?.status === "completed" && displayTrial ? (
        <Card
          title={sweep.best_valid ? "Best Config" : "No Valid Best Config"}
          subtitle={
            sweep.best_valid
              ? "Selected by composite score on test data"
              : "No trial met minimum trade guardrails"
          }
        >
          <div className="space-y-4">
            {!sweep.best_valid && sweep.selection_message ? (
              <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                {sweep.selection_message}
              </p>
            ) : null}
            {sweep.best_valid && bestBelowMinTrades ? (
              <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                Warning: best config has only {sweep.best?.test_total_trades}{" "}
                test trades (minimum requested: {minTrades}).
              </p>
            ) : null}
            {!sweep.best_valid ? (
              <p className="text-sm text-muted">
                Closest candidate by test trades (not recommended to apply):
              </p>
            ) : null}
            <p className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3 text-xs text-muted">
              Return shows test-period PnL for Top-K finalists (highlighted
              rows). Other trials show train-period return. A dash means the
              sweep is still running or metrics were not computed yet.
            </p>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-muted">Composite</p>
                <p className="text-lg font-semibold">
                  {displayTrial.composite_score != null &&
                  Number.isFinite(displayTrial.composite_score)
                    ? displayTrial.composite_score.toFixed(1)
                    : displayTrial.test_score != null
                      ? "ineligible"
                      : "—"}
                </p>
              </div>
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-muted">Test score</p>
                <p className="text-lg font-semibold">
                  {displayTrial.test_score?.toFixed(1) ?? "—"}
                </p>
              </div>
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-muted">Test return</p>
                <p className="text-lg font-semibold">
                  {displayTrial.test_score != null &&
                  displayTrial.test_return_pct != null
                    ? `${displayTrial.test_return_pct.toFixed(2)}%`
                    : displayTrial.train_return_pct != null
                      ? `${displayTrial.train_return_pct.toFixed(2)}% (train)`
                      : "—"}
                </p>
              </div>
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-muted">Stability</p>
                <p className="text-lg font-semibold">
                  {displayTrial.stability != null
                    ? `${(displayTrial.stability * 100).toFixed(0)}%`
                    : "—"}
                </p>
              </div>
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-muted">Test trades</p>
                <p className="text-lg font-semibold">
                  {displayTrial.test_total_trades ?? "—"}
                </p>
              </div>
            </div>
            <p className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3 text-xs text-muted">
              Composite = 60% test score + 25% stability + 15% return term −
              fold std penalty. Trials below min trades or min return are
              excluded.
            </p>
            <p className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3 font-mono text-xs">
              {fmtParams(displayTrial.params)}
            </p>
            {enabledProviderChips(displayTrial.params).length > 0 ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase text-muted">
                  Active providers
                </span>
                {enabledProviderChips(displayTrial.params).map((chip) => (
                  <Badge key={chip} variant="accent">
                    {chip}
                  </Badge>
                ))}
                {displayTrial.params.min_agreeing_providers != null ? (
                  <Badge variant="default">
                    agree ≥ {String(displayTrial.params.min_agreeing_providers)}
                  </Badge>
                ) : null}
              </div>
            ) : null}
            {sweep.holdout_metrics &&
            sweep.holdout_start &&
            sweep.holdout_end ? (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium text-foreground">
                    Holdout ({sweep.holdout_start.slice(0, 10)} →{" "}
                    {sweep.holdout_end.slice(0, 10)})
                  </p>
                  <Badge
                    variant={sweep.holdout_valid ? "success" : "danger"}
                    dot
                  >
                    {sweep.holdout_valid ? "Passed" : "Failed"}
                  </Badge>
                </div>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                  <div className="rounded-lg border border-[var(--border)] p-3">
                    <p className="text-xs text-muted">Holdout score</p>
                    <p className="text-lg font-semibold">
                      {sweep.holdout_score?.toFixed(1) ?? "—"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--border)] p-3">
                    <p className="text-xs text-muted">Holdout return</p>
                    <p className="text-lg font-semibold">
                      {sweep.holdout_metrics.return_pct != null
                        ? `${sweep.holdout_metrics.return_pct.toFixed(2)}%`
                        : "—"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--border)] p-3">
                    <p className="text-xs text-muted">Holdout trades</p>
                    <p className="text-lg font-semibold">
                      {sweep.holdout_metrics.total_trades ?? "—"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--border)] p-3">
                    <p className="text-xs text-muted">Max drawdown</p>
                    <p className="text-lg font-semibold">
                      {sweep.holdout_metrics.max_drawdown_pct != null
                        ? `${sweep.holdout_metrics.max_drawdown_pct.toFixed(1)}%`
                        : "—"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--border)] p-3">
                    <p className="text-xs text-muted">Sharpe (daily)</p>
                    <p className="text-lg font-semibold">
                      {sweep.holdout_metrics.sharpe_ratio?.toFixed(2) ?? "—"}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}
            <div className="flex flex-wrap gap-3">
              {sweep.holdout_start && sweep.holdout_end ? (
                <button
                  type="button"
                  onClick={() => validateHoldout.mutate()}
                  disabled={validateHoldout.isPending || !displayTrial}
                  className="btn-secondary"
                >
                  {validateHoldout.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ShieldCheck className="h-4 w-4" />
                  )}
                  Validate Holdout
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => apply.mutate(!sweep.best_valid)}
                disabled={
                  apply.isPending ||
                  sweep.status !== "completed" ||
                  !displayTrial
                }
                className="btn-primary"
              >
                {apply.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <PlayCircle className="h-4 w-4" />
                )}
                {sweep.best_valid
                  ? "Apply best config"
                  : "Apply candidate config"}
              </button>
            </div>
            {validateHoldout.error ? (
              <p className="text-sm text-danger">
                {validateHoldout.error instanceof Error
                  ? validateHoldout.error.message
                  : "Holdout validation failed to start"}
              </p>
            ) : null}
            {apply.data?.revision_id ? (
              <p className="text-sm text-[var(--success)]">
                Applied ({apply.data.applied_from ?? "best"}) — revision{" "}
                {apply.data.revision_id}
              </p>
            ) : null}
            {apply.error ? (
              <p className="text-sm text-danger">
                {apply.error instanceof Error
                  ? apply.error.message
                  : "Apply failed"}
              </p>
            ) : null}
          </div>
        </Card>
      ) : null}

      {sweep?.trials?.length ? (
        <Card
          title="Trials"
          subtitle="Train scores for all candidates — click a row for test details"
        >
          <OptimizationTrialsTable
            trials={sweep.trials}
            topTrialIds={topTrialIds}
            topK={topK}
          />
        </Card>
      ) : null}
    </div>
  );
}
