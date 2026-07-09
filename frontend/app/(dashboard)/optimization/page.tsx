"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, PlayCircle, Sparkles } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { DateRangeFields } from "@/components/ui/DateRangeFields";
import { api } from "@/lib/api";
import { dateRangeForPreset } from "@/lib/dateRange";

function fmtParams(params: Record<string, number | string>) {
  return Object.entries(params)
    .map(([k, v]) => `${k.replace(/_/g, " ")}=${v}`)
    .join(" · ");
}

const DEFAULT_RANGE = dateRangeForPreset("90d");
const DEFAULT_SPACE = {
  min_confidence: [0.6, 0.7, 0.78],
  min_risk_reward: [1.0, 1.5, 2.0],
  min_agreeing_providers: [1, 2],
  sl_atr_mult: [1.0, 1.5, 2.0],
  tp_atr_mult: [2.0, 3.0, 4.0],
  max_bars_in_trade: [12, 24, 48],
  oversold: [25, 30, 35],
  overbought: [65, 70, 75],
  risk_pct_per_trade: [0.5, 1.0, 1.5],
  min_atr_pct: [0.1, 0.3, 0.5],
  session_preset: ["eu_us", "all"],
  max_signals_per_day: [5, 10, 20],
  ema_fast: [10, 12, 14],
  ema_slow: [24, 26, 30],
  rsi_period: [12, 14, 16],
  ema_weight: [1.0],
  rsi_weight: [1.0],
  ema_enabled: [1],
  rsi_enabled: [1],
};

export default function OptimizationPage() {
  const queryClient = useQueryClient();
  const [sweepId, setSweepId] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [startDate, setStartDate] = useState(DEFAULT_RANGE.start);
  const [endDate, setEndDate] = useState(DEFAULT_RANGE.end);
  const [initialCapital, setInitialCapital] = useState(10000);
  const [trainRatio, setTrainRatio] = useState(0.7);
  const [maxTrials, setMaxTrials] = useState(36);
  const [topK, setTopK] = useState(5);
  const [minTrades, setMinTrades] = useState(20);
  const [walkForwardWindows, setWalkForwardWindows] = useState(3);
  const [holdoutRatio, setHoldoutRatio] = useState(0.2);

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
        local_refine: true,
        space: DEFAULT_SPACE,
      }),
    onSuccess: (res) => setSweepId(res.id),
  });

  const { data: sweep } = useQuery({
    queryKey: ["optimization", sweepId],
    queryFn: () => api.optimization(sweepId!),
    enabled: !!sweepId,
    refetchInterval: (q) =>
      q.state.data?.status === "completed" || q.state.data?.status === "failed"
        ? false
        : 2000,
  });

  const isSweepActive =
    sweep?.status === "pending" || sweep?.status === "running";

  const apply = useMutation({
    mutationFn: () => api.applyOptimization(sweepId!),
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
    sweep?.best?.test_total_trades != null &&
    sweep.best.test_total_trades < minTrades;

  return (
    <div className="page-container">
      <PageHeader
        title="Auto Optimizer"
        description="Walk-forward grid search with composite scoring, holdout reserve, and local refinement."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          title="Sweep Configuration"
          subtitle="Train/test split with walk-forward folds"
        >
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium uppercase tracking-wider text-muted">
                Symbol
              </label>
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
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  Train Ratio
                </label>
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
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  Initial Capital
                </label>
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
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  Max Trials
                </label>
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
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  Top K (test)
                </label>
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
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  Min Trades
                </label>
                <input
                  type="number"
                  min={0}
                  className="input-field mt-2"
                  value={minTrades}
                  onChange={(e) => setMinTrades(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  WF Windows
                </label>
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
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  Holdout Ratio
                </label>
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
            <p className="text-xs text-muted">
              Last {Math.round(holdoutRatio * 100)}% of the date range is
              reserved as holdout. Validate manually on that period after Apply.
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

      {sweep?.best ? (
        <Card
          title="Best Config"
          subtitle="Selected by composite score on test data"
        >
          <div className="space-y-4">
            {bestBelowMinTrades ? (
              <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                Warning: best config has only {sweep.best.test_total_trades}{" "}
                test trades (minimum requested: {minTrades}).
              </p>
            ) : null}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-muted">Composite</p>
                <p className="text-lg font-semibold">
                  {sweep.best.composite_score?.toFixed(1) ?? "—"}
                </p>
              </div>
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-muted">Test score</p>
                <p className="text-lg font-semibold">
                  {sweep.best.test_score?.toFixed(1) ?? "—"}
                </p>
              </div>
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-muted">Test return</p>
                <p className="text-lg font-semibold">
                  {sweep.best.test_return_pct != null
                    ? `${sweep.best.test_return_pct.toFixed(2)}%`
                    : "—"}
                </p>
              </div>
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-muted">Stability</p>
                <p className="text-lg font-semibold">
                  {sweep.best.stability != null
                    ? `${(sweep.best.stability * 100).toFixed(0)}%`
                    : "—"}
                </p>
              </div>
              <div className="rounded-lg border border-[var(--border)] p-3">
                <p className="text-xs text-muted">Test trades</p>
                <p className="text-lg font-semibold">
                  {sweep.best.test_total_trades ?? "—"}
                </p>
              </div>
            </div>
            <p className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3 text-xs text-muted">
              Composite = 60% test score + 25% stability + 15% return term −
              fold std penalty. Trials below min trades or min return are
              excluded.
            </p>
            <p className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3 font-mono text-xs">
              {fmtParams(sweep.best.params)}
            </p>
            {sweep.holdout_start && sweep.holdout_end ? (
              <p className="text-sm text-muted">
                After Apply, run Validation on holdout period{" "}
                <strong className="text-foreground">
                  {sweep.holdout_start.slice(0, 10)} →{" "}
                  {sweep.holdout_end.slice(0, 10)}
                </strong>{" "}
                to confirm out-of-sample performance.
              </p>
            ) : null}
            <button
              type="button"
              onClick={() => apply.mutate()}
              disabled={apply.isPending || sweep.status !== "completed"}
              className="btn-primary"
            >
              {apply.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <PlayCircle className="h-4 w-4" />
              )}
              Apply best config
            </button>
            {apply.data?.revision_id ? (
              <p className="text-sm text-[var(--success)]">
                Applied — revision {apply.data.revision_id}
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
        <Card title="Trials" subtitle="All parameter combinations evaluated">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
                  <th className="pb-2 pr-3">Params</th>
                  <th className="pb-2 pr-3">Train</th>
                  <th className="pb-2 pr-3">Test</th>
                  <th className="pb-2 pr-3">Return</th>
                  <th className="pb-2 pr-3">Trades</th>
                  <th className="pb-2 pr-3">Composite</th>
                  <th className="pb-2">Stability</th>
                </tr>
              </thead>
              <tbody>
                {sweep.trials
                  .slice()
                  .sort(
                    (a, b) =>
                      (b.composite_score ?? b.test_score ?? b.train_score) -
                      (a.composite_score ?? a.test_score ?? a.train_score),
                  )
                  .map((trial) => (
                    <tr
                      key={trial.trial_id}
                      className={`border-b border-[var(--border)]/50 ${
                        topTrialIds.has(trial.trial_id)
                          ? "bg-[var(--accent-dim)]/30"
                          : ""
                      }`}
                    >
                      <td className="py-2 pr-3 font-mono text-xs">
                        {fmtParams(trial.params)}
                      </td>
                      <td className="py-2 pr-3">
                        {trial.train_score.toFixed(1)}
                      </td>
                      <td className="py-2 pr-3">
                        {trial.test_score != null
                          ? trial.test_score.toFixed(1)
                          : "—"}
                      </td>
                      <td className="py-2 pr-3">
                        {trial.test_return_pct != null
                          ? `${trial.test_return_pct.toFixed(1)}%`
                          : "—"}
                      </td>
                      <td className="py-2 pr-3">
                        {trial.test_total_trades ?? "—"}
                      </td>
                      <td className="py-2 pr-3">
                        {trial.composite_score != null
                          ? trial.composite_score.toFixed(1)
                          : "—"}
                      </td>
                      <td className="py-2">
                        {trial.stability != null
                          ? `${(trial.stability * 100).toFixed(0)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
