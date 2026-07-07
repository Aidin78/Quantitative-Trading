"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, PlayCircle } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ValidationMetricsPanel } from "@/components/validation/ValidationMetricsPanel";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function ValidationPage() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [startDate, setStartDate] = useState("2026-01-01");

  const run = useMutation({
    mutationFn: () =>
      api.runValidation({ symbol, start_date: startDate, timeframe: "1h" }),
    onSuccess: (res) => setJobId(res.id),
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
              <div className="flex items-center gap-3">
                <Badge variant={statusVariant} dot>
                  {job.status}
                </Badge>
                {(job.status === "pending" || job.status === "running") && (
                  <Loader2 className="h-4 w-4 animate-spin text-accent" />
                )}
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
    </div>
  );
}
