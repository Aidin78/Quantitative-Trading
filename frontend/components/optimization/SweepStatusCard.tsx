"use client";

import { Loader2 } from "lucide-react";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import type { OptimizationSweep } from "@/lib/api";

type Props = {
  sweepId: string | null;
  sweep: OptimizationSweep | null | undefined;
  isSweepActive: boolean;
  progressPct: number;
  statusVariant: "success" | "danger" | "accent";
  isCancelPending: boolean;
  onCancel: () => void;
};

export function SweepStatusCard({
  sweepId,
  sweep,
  isSweepActive,
  progressPct,
  statusVariant,
  isCancelPending,
  onCancel,
}: Props) {
  return (
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
              <>
                <Loader2 className="h-4 w-4 animate-spin text-accent" />
                <button
                  type="button"
                  onClick={onCancel}
                  disabled={isCancelPending || !sweepId}
                  className="btn-secondary text-xs"
                >
                  {isCancelPending ? "Cancelling…" : "Cancel"}
                </button>
              </>
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
                  {sweep.progress.current} / {sweep.progress.total} backtests (
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

          {sweep.status === "completed" ? (
            <p className="rounded-lg border border-[var(--success)]/20 bg-[var(--success-dim)] p-3 text-sm text-[var(--success)]">
              Sweep complete. Review composite score and holdout dates below.
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
              {sweep.test_start?.slice(0, 10)} → {sweep.test_end.slice(0, 10)}
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
  );
}
