"use client";

import { Download, Loader2 } from "lucide-react";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import type { ValidationJob } from "@/lib/api";

const PHASE_LABELS: Record<string, string> = {
  data: "Loading data",
  backtest: "Backtesting",
  metrics: "Computing metrics",
  persist: "Saving results",
};

type Props = {
  jobId: string | null;
  job: ValidationJob | null | undefined;
  isJobActive: boolean;
  progressPct: number;
  statusVariant: "success" | "danger" | "accent";
  isCancelPending: boolean;
  onCancel: () => void;
  exporting: boolean;
  exportError: string | null;
  onExport: () => void;
};

export function ValidationStatusCard({
  jobId,
  job,
  isJobActive,
  progressPct,
  statusVariant,
  isCancelPending,
  onCancel,
  exporting,
  exportError,
  onExport,
}: Props) {
  return (
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
              <>
                <Loader2 className="h-4 w-4 animate-spin text-accent" />
                <button
                  type="button"
                  onClick={onCancel}
                  disabled={isCancelPending || !jobId}
                  className="btn-secondary text-xs"
                >
                  {isCancelPending ? "Cancelling…" : "Cancel"}
                </button>
              </>
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
                onClick={onExport}
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
  );
}
