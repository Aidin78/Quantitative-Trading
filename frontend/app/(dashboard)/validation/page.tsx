"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, Loader2, PlayCircle } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ValidationMetricsPanel } from "@/components/validation/ValidationMetricsPanel";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function ValidationPage() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [startDate, setStartDate] = useState("2026-01-01");
  const [wfWindows, setWfWindows] = useState(3);
  const [wfTrainRatio, setWfTrainRatio] = useState(0.7);
  const [exporting, setExporting] = useState(false);

  const run = useMutation({
    mutationFn: () =>
      api.runValidation({ symbol, start_date: startDate, timeframe: "1h" }),
    onSuccess: (res) => setJobId(res.id),
  });

  const walkForward = useMutation({
    mutationFn: () =>
      api.walkForward({
        symbol,
        start_date: startDate,
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

  const statusVariant =
    job?.status === "completed"
      ? "success"
      : job?.status === "failed"
        ? "danger"
        : "accent";

  async function handleExport() {
    if (!jobId) return;
    setExporting(true);
    try {
      await api.exportValidation(jobId);
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
        <Card title="Run Configuration" subtitle="Historical CSV validation">
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
            <div>
              <label className="text-xs font-medium uppercase tracking-wider text-muted">
                Start Date
              </label>
              <input
                className="input-field mt-2"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <button
              type="button"
              onClick={() => run.mutate()}
              disabled={run.isPending}
              className="btn-primary w-full"
            >
              {run.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <PlayCircle className="h-4 w-4" />
              )}
              Run Validation
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
                {(job.status === "pending" || job.status === "running") && (
                  <Loader2 className="h-4 w-4 animate-spin text-accent" />
                )}
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
              {job.error && (
                <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                  {job.error}
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
          />
        </Card>
      )}

      <Card title="Walk-Forward" subtitle="Rolling window validation">
        <div className="mb-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="text-xs font-medium uppercase tracking-wider text-muted">
              Windows
            </label>
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
            <label className="text-xs font-medium uppercase tracking-wider text-muted">
              Train Ratio
            </label>
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
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
