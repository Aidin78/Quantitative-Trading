"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Loader2, PlayCircle, Trash2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ValidationMetricsPanel } from "@/components/validation/ValidationMetricsPanel";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { DateRangeFields } from "@/components/ui/DateRangeFields";
import { FieldLabel } from "@/components/ui/FieldLabel";
import { api } from "@/lib/api";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";
import { dateRangeForPreset } from "@/lib/dateRange";

const PHASE_LABELS: Record<string, string> = {
  data: "Loading data",
  backtest: "Backtesting",
  metrics: "Computing metrics",
  persist: "Saving results",
};

export default function ValidationPage() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const [jobId, setJobId] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [startDate, setStartDate] = useState(
    () => dateRangeForPreset("30d").start,
  );
  const [endDate, setEndDate] = useState(() => dateRangeForPreset("30d").end);
  const [initialCapital, setInitialCapital] = useState(10000);
  const [wfWindows, setWfWindows] = useState(3);
  const [wfTrainRatio, setWfTrainRatio] = useState(0.7);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [compareRunA, setCompareRunA] = useState<string>("");
  const [compareRunB, setCompareRunB] = useState<string>("");
  const [selectedRuns, setSelectedRuns] = useState<Set<string>>(new Set());
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    const job = searchParams.get("job");
    if (job) setJobId(job);
    const sym = searchParams.get("symbol");
    if (sym) setSymbol(sym);
    const start = searchParams.get("start");
    if (start) setStartDate(start);
    const end = searchParams.get("end");
    if (end) setEndDate(end);
  }, [searchParams]);

  const { data: runHistory } = useQuery({
    queryKey: ["validation-runs", symbol],
    queryFn: () => api.validationRuns({ limit: 20, symbol }),
  });

  const { data: compareData } = useQuery({
    queryKey: ["validation-compare", compareRunA, compareRunB],
    queryFn: () => api.validationCompare(compareRunA, compareRunB),
    enabled: !!compareRunA && !!compareRunB && compareRunA !== compareRunB,
  });

  const run = useMutation({
    mutationFn: () =>
      api.runValidation({
        symbol,
        start_date: startDate,
        end_date: endDate || undefined,
        source: "exchange",
        initial_capital: initialCapital,
        timeframe: "1h",
      }),
    onSuccess: (res) => setJobId(res.id),
  });

  const walkForward = useMutation({
    mutationFn: () =>
      api.walkForward({
        symbol,
        start_date: startDate,
        end_date: endDate || undefined,
        source: "exchange",
        initial_capital: initialCapital,
        timeframe: "1h",
        windows: wfWindows,
        train_ratio: wfTrainRatio,
      }),
  });

  const { data: job } = useQuery({
    queryKey: ["validation", jobId],
    queryFn: () => api.validation(jobId!),
    enabled: !!jobId,
    refetchInterval: (q) =>
      q.state.data?.status === "completed" || q.state.data?.status === "failed"
        ? false
        : 2000,
  });

  const { data: tradesData } = useQuery({
    queryKey: ["validation-trades", jobId],
    queryFn: () => api.validationTrades(jobId!),
    enabled: !!jobId && job?.status === "completed",
  });

  const statusVariant =
    job?.status === "completed"
      ? "success"
      : job?.status === "failed"
        ? "danger"
        : "accent";

  const isJobActive = job?.status === "pending" || job?.status === "running";

  const progressPct =
    job?.progress && job.progress.total > 0
      ? Math.round((job.progress.current / job.progress.total) * 100)
      : 0;

  const historyItems = runHistory?.items ?? [];
  const allHistorySelected =
    historyItems.length > 0 && selectedRuns.size === historyItems.length;
  const someHistorySelected = selectedRuns.size > 0;
  const selectedRunIds = useMemo(
    () => Array.from(selectedRuns),
    [selectedRuns],
  );

  useEffect(() => {
    if (job?.status === "completed") {
      queryClient.invalidateQueries({ queryKey: ["validation-runs"] });
    }
  }, [job?.status, queryClient]);

  const invalidateHistory = () => {
    queryClient.invalidateQueries({ queryKey: ["validation-runs"] });
    setSelectedRuns(new Set());
  };

  const deleteOneRun = useMutation({
    mutationFn: (runId: string) => api.deleteValidationRun(runId),
    onSuccess: (_data, runId) => {
      setHistoryError(null);
      if (jobId === runId) setJobId(null);
      if (compareRunA === runId) setCompareRunA("");
      if (compareRunB === runId) setCompareRunB("");
      invalidateHistory();
    },
    onError: (err) => {
      setHistoryError(err instanceof Error ? err.message : "Delete failed");
    },
  });

  const deleteManyRuns = useMutation({
    mutationFn: (runIds: string[]) => api.deleteValidationRuns(runIds),
    onSuccess: (result) => {
      setHistoryError(null);
      if (jobId && result.deleted.includes(jobId)) setJobId(null);
      if (compareRunA && result.deleted.includes(compareRunA)) {
        setCompareRunA("");
      }
      if (compareRunB && result.deleted.includes(compareRunB)) {
        setCompareRunB("");
      }
      invalidateHistory();
    },
    onError: (err) => {
      setHistoryError(
        err instanceof Error ? err.message : "Bulk delete failed",
      );
    },
  });

  const isDeletingHistory = deleteOneRun.isPending || deleteManyRuns.isPending;

  function toggleRunSelection(runId: string) {
    setSelectedRuns((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) next.delete(runId);
      else next.add(runId);
      return next;
    });
  }

  function toggleAllHistory() {
    if (allHistorySelected) {
      setSelectedRuns(new Set());
      return;
    }
    setSelectedRuns(new Set(historyItems.map((row) => row.run_id)));
  }

  function confirmDeleteRun(runId: string) {
    if (
      !window.confirm(
        "Delete this validation run from history? Simulated trades for this run will also be removed.",
      )
    ) {
      return;
    }
    deleteOneRun.mutate(runId);
  }

  function confirmDeleteSelectedRuns() {
    if (!selectedRunIds.length) return;
    if (
      !window.confirm(
        `Delete ${selectedRunIds.length} selected validation run(s)? This cannot be undone.`,
      )
    ) {
      return;
    }
    deleteManyRuns.mutate(selectedRunIds);
  }

  async function handleExport() {
    if (!jobId) return;
    setExporting(true);
    setExportError(null);
    try {
      await api.exportValidation(jobId);
    } catch (err) {
      let msg = err instanceof Error ? err.message : "Export failed";
      try {
        const parsed = JSON.parse(msg);
        if (parsed?.detail) msg = parsed.detail;
      } catch {
        // message was not JSON; keep as-is
      }
      setExportError(msg);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="page-container">
      <PageHeader
        title="Validation Harness"
        description="Run historical backtests to measure engine quality and outcome metrics."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          title="Run Configuration"
          subtitle="Historical validation with live exchange data"
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
              startDate={startDate}
              endDate={endDate}
              onStartDateChange={setStartDate}
              onEndDateChange={setEndDate}
            />
            <div>
              <FieldLabel
                label="Initial Capital"
                tooltip={FORM_TOOLTIPS.initialCapital}
              />
              <input
                type="number"
                min={100}
                step={100}
                className="input-field mt-2"
                value={initialCapital}
                onChange={(e) => setInitialCapital(Number(e.target.value))}
              />
            </div>
            {(run.error || walkForward.error) && (
              <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                {run.error instanceof Error
                  ? run.error.message
                  : walkForward.error instanceof Error
                    ? walkForward.error.message
                    : "Validation request failed"}
              </p>
            )}
            <button
              type="button"
              onClick={() => run.mutate()}
              disabled={run.isPending || isJobActive}
              className="btn-primary w-full"
            >
              {run.isPending || isJobActive ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <PlayCircle className="h-4 w-4" />
              )}
              {isJobActive ? "Validation running…" : "Run Validation"}
            </button>
          </div>
        </Card>

        <Card
          title="Job Status"
          subtitle={jobId ? `ID: ${jobId}` : "No active job"}
        >
          {!job ? (
            <EmptyState
              message="No validation job yet"
              hint="Configure and run a harness above"
            />
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant={statusVariant} dot>
                  {job.status}
                </Badge>
                {job.phase && isJobActive ? (
                  <Badge variant="accent">
                    {PHASE_LABELS[job.phase] ?? job.phase}
                  </Badge>
                ) : null}
                {isJobActive && (
                  <Loader2 className="h-4 w-4 animate-spin text-accent" />
                )}
                {job.elapsed_seconds != null ? (
                  <span className="ml-auto text-xs text-muted">
                    {job.elapsed_seconds < 60
                      ? `${Math.round(job.elapsed_seconds)}s`
                      : `${Math.floor(job.elapsed_seconds / 60)}m ${Math.round(
                          job.elapsed_seconds % 60,
                        )}s`}
                  </span>
                ) : null}
                {job.status === "completed" ? (
                  <button
                    type="button"
                    onClick={handleExport}
                    disabled={exporting}
                    className="btn-secondary text-xs"
                  >
                    {exporting ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Download className="h-3 w-3" />
                    )}
                    Export CSV
                  </button>
                ) : null}
              </div>

              {isJobActive ? (
                <p className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/60 p-3 text-sm text-foreground">
                  {job.message ||
                    (job.status === "pending"
                      ? "Queued — starting validation…"
                      : "Working…")}
                </p>
              ) : null}

              {job.progress && isJobActive && job.progress.total > 0 ? (
                <div>
                  <div className="mb-1 flex justify-between text-xs text-muted">
                    <span>Bar simulation</span>
                    <span>
                      {job.progress.current} / {job.progress.total} bars (
                      {progressPct}%)
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

              {job.status === "completed" ? (
                <p className="rounded-lg border border-[var(--success)]/20 bg-[var(--success-dim)] p-3 text-sm text-[var(--success)]">
                  Validation complete
                  {job.elapsed_seconds != null
                    ? ` in ${
                        job.elapsed_seconds < 60
                          ? `${Math.round(job.elapsed_seconds)}s`
                          : `${Math.floor(job.elapsed_seconds / 60)}m`
                      }`
                    : ""}
                  . Results are shown below.
                </p>
              ) : null}

              {job.error && (
                <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                  {job.error}
                </p>
              )}
              {exportError && (
                <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                  {exportError}
                </p>
              )}
            </div>
          )}
        </Card>
      </div>

      {job?.engine_metrics && (
        <Card title="Validation Results" subtitle="Engine and outcome metrics">
          <ValidationMetricsPanel
            engine={job.engine_metrics}
            outcome={job.outcome_metrics}
            trades={tradesData?.trades}
          />
        </Card>
      )}

      <Card title="Run History" subtitle="Past validation runs from database">
        {historyItems.length ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
                <input
                  type="checkbox"
                  checked={allHistorySelected}
                  ref={(el) => {
                    if (el) {
                      el.indeterminate =
                        someHistorySelected && !allHistorySelected;
                    }
                  }}
                  onChange={toggleAllHistory}
                  disabled={isDeletingHistory}
                />
                Select all
              </label>
              {someHistorySelected ? (
                <button
                  type="button"
                  onClick={confirmDeleteSelectedRuns}
                  disabled={isDeletingHistory}
                  className="btn-secondary border-danger/30 text-danger hover:border-danger/50"
                >
                  {deleteManyRuns.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  Delete selected ({selectedRuns.size})
                </button>
              ) : null}
            </div>

            {historyError ? (
              <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                {historyError}
              </p>
            ) : null}

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
                    <th className="pb-2 pr-2 w-8" />
                    <th className="pb-2 pr-3">Period</th>
                    <th className="pb-2 pr-3">Trades</th>
                    <th className="pb-2 pr-3">Return</th>
                    <th className="pb-2 pr-3">Score</th>
                    <th className="pb-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {historyItems.map((row) => (
                    <tr
                      key={row.run_id}
                      className="border-b border-[var(--border)]/50"
                    >
                      <td className="py-2 pr-2">
                        <input
                          type="checkbox"
                          checked={selectedRuns.has(row.run_id)}
                          onChange={() => toggleRunSelection(row.run_id)}
                          disabled={isDeletingHistory}
                          aria-label={`Select run ${row.run_id}`}
                        />
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {row.start?.slice(0, 10) ?? "—"} →{" "}
                        {row.end?.slice(0, 10) ?? "—"}
                      </td>
                      <td className="py-2 pr-3">{row.total_trades}</td>
                      <td
                        className={`py-2 pr-3 font-mono text-xs ${row.return_pct >= 0 ? "text-[var(--success)]" : "text-danger"}`}
                      >
                        {row.return_pct.toFixed(2)}%
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {row.score.toFixed(1)}
                      </td>
                      <td className="py-2">
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            className="btn-secondary text-xs"
                            onClick={() => setJobId(row.run_id)}
                          >
                            View
                          </button>
                          <button
                            type="button"
                            className="btn-secondary border-danger/30 px-2 py-1 text-xs text-danger hover:border-danger/50"
                            onClick={() => confirmDeleteRun(row.run_id)}
                            disabled={isDeletingHistory}
                            aria-label={`Delete run ${row.run_id}`}
                          >
                            {deleteOneRun.isPending &&
                            deleteOneRun.variables === row.run_id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Trash2 className="h-3 w-3" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <EmptyState
            message="No saved runs yet"
            hint="Run a validation with database persistence enabled"
          />
        )}
      </Card>

      <Card title="Compare Runs" subtitle="Side-by-side metrics for two runs">
        <div className="mb-4 grid gap-4 sm:grid-cols-2">
          <div>
            <FieldLabel label="Run A" tooltip={FORM_TOOLTIPS.compareRunA} />
            <select
              className="input-field mt-2"
              value={compareRunA}
              onChange={(e) => setCompareRunA(e.target.value)}
            >
              <option value="">Select run…</option>
              {runHistory?.items.map((row) => (
                <option key={`a-${row.run_id}`} value={row.run_id}>
                  {row.start?.slice(0, 10)} → {row.end?.slice(0, 10)} (score{" "}
                  {row.score.toFixed(1)})
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel label="Run B" tooltip={FORM_TOOLTIPS.compareRunB} />
            <select
              className="input-field mt-2"
              value={compareRunB}
              onChange={(e) => setCompareRunB(e.target.value)}
            >
              <option value="">Select run…</option>
              {runHistory?.items.map((row) => (
                <option key={`b-${row.run_id}`} value={row.run_id}>
                  {row.start?.slice(0, 10)} → {row.end?.slice(0, 10)} (score{" "}
                  {row.score.toFixed(1)})
                </option>
              ))}
            </select>
          </div>
        </div>

        {compareRunA && compareRunB && compareRunA === compareRunB ? (
          <p className="text-sm text-muted">Select two different runs.</p>
        ) : null}

        {compareData ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <Badge
                variant={
                  compareData.overall_winner === "tie" ? "accent" : "success"
                }
              >
                Overall winner: {compareData.overall_winner.toUpperCase()}
              </Badge>
              {compareData.revision_diff?.same_revision === false ? (
                <span className="text-xs text-muted">
                  Different config revisions
                </span>
              ) : null}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
                    <th className="pb-2 pr-3">Metric</th>
                    <th className="pb-2 pr-3">Run A</th>
                    <th className="pb-2 pr-3">Run B</th>
                    <th className="pb-2 pr-3">Delta</th>
                    <th className="pb-2">Winner</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(compareData.metrics).map(([key, metric]) => (
                    <tr
                      key={key}
                      className="border-b border-[var(--border)]/50"
                    >
                      <td className="py-2 pr-3">{key.replace(/_/g, " ")}</td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {typeof metric.a === "number"
                          ? metric.a.toFixed(2)
                          : metric.a}
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {typeof metric.b === "number"
                          ? metric.b.toFixed(2)
                          : metric.b}
                      </td>
                      <td
                        className={`py-2 pr-3 font-mono text-xs ${metric.delta >= 0 ? "text-[var(--success)]" : "text-danger"}`}
                      >
                        {metric.delta >= 0 ? "+" : ""}
                        {metric.delta.toFixed(2)}
                      </td>
                      <td className="py-2 text-xs uppercase">
                        {metric.winner}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </Card>

      <Card title="Walk-Forward" subtitle="Rolling window validation">
        <div className="mb-4 grid gap-4 sm:grid-cols-2">
          <div>
            <FieldLabel label="Windows" tooltip={FORM_TOOLTIPS.wfWindows} />
            <input
              type="number"
              min={2}
              max={10}
              className="input-field mt-2"
              value={wfWindows}
              onChange={(e) => setWfWindows(Number(e.target.value))}
            />
          </div>
          <div>
            <FieldLabel
              label="Train Ratio"
              tooltip={FORM_TOOLTIPS.wfTrainRatio}
            />
            <input
              type="number"
              min={0.1}
              max={0.9}
              step={0.1}
              className="input-field mt-2"
              value={wfTrainRatio}
              onChange={(e) => setWfTrainRatio(Number(e.target.value))}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={() => walkForward.mutate()}
          disabled={walkForward.isPending}
          className="btn-primary"
        >
          {walkForward.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <PlayCircle className="h-4 w-4" />
          )}
          Run Walk-Forward
        </button>

        {walkForward.data?.windows.length ? (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
                  <th className="pb-2 pr-4">Window</th>
                  <th className="pb-2 pr-4">Test Period</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2">Trades</th>
                </tr>
              </thead>
              <tbody>
                {walkForward.data.windows.map((w) => (
                  <tr
                    key={w.window}
                    className="border-b border-[var(--border)]/50"
                  >
                    <td className="py-2 pr-4">{w.window + 1}</td>
                    <td className="py-2 pr-4 font-mono text-xs">
                      {w.test_start.slice(0, 10)} → {w.test_end.slice(0, 10)}
                    </td>
                    <td className="py-2 pr-4">
                      <Badge
                        variant={
                          w.status === "completed" ? "success" : "danger"
                        }
                      >
                        {w.status}
                      </Badge>
                    </td>
                    <td className="py-2">
                      {w.outcome_metrics?.total_trades != null
                        ? String(w.outcome_metrics.total_trades)
                        : w.error
                          ? "—"
                          : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {walkForward.data.windows.some((w) => w.error) ? (
              <div className="mt-4 space-y-2">
                {walkForward.data.windows
                  .filter((w) => w.error)
                  .map((w) => (
                    <p
                      key={`err-${w.window}`}
                      className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger"
                    >
                      Window {w.window + 1}: {w.error}
                    </p>
                  ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
