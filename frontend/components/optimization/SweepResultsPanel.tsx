"use client";

import { Loader2, PlayCircle, ShieldCheck } from "lucide-react";
import { Badge, Card } from "@/components/ui/Card";
import type {
  OptimizationApplyResponse,
  OptimizationSweep,
  OptimizationTrial,
} from "@/lib/api";
import {
  enabledProviderChips,
  fmtParamsWithoutEnabled,
} from "@/lib/optimizationSpaces";

function fmtParams(params: Record<string, number | string>) {
  return fmtParamsWithoutEnabled(params);
}

type Props = {
  sweep: OptimizationSweep;
  displayTrial: OptimizationTrial;
  minTrades: number;
  bestBelowMinTrades: boolean;
  isValidatePending: boolean;
  validateError: Error | null;
  onValidateHoldout: () => void;
  isApplyPending: boolean;
  applyData: OptimizationApplyResponse | undefined;
  applyError: Error | null;
  onApply: () => void;
};

export function SweepResultsPanel({
  sweep,
  displayTrial,
  minTrades,
  bestBelowMinTrades,
  isValidatePending,
  validateError,
  onValidateHoldout,
  isApplyPending,
  applyData,
  applyError,
  onApply,
}: Props) {
  return (
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
            Warning: best config has only {sweep.best?.test_total_trades} test
            trades (minimum requested: {minTrades}).
          </p>
        ) : null}
        {!sweep.best_valid ? (
          <p className="text-sm text-muted">
            Closest candidate by test trades (not recommended to apply):
          </p>
        ) : null}
        <p className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3 text-xs text-muted">
          Return shows test-period PnL for Top-K finalists (highlighted rows).
          Other trials show train-period return. A dash means the sweep is still
          running or metrics were not computed yet.
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
          Composite = 60% test score + 25% stability + 15% return term − fold
          std penalty. Trials below min trades or min return are excluded.
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
        {sweep.holdout_metrics && sweep.holdout_start && sweep.holdout_end ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-foreground">
                Holdout ({sweep.holdout_start.slice(0, 10)} →{" "}
                {sweep.holdout_end.slice(0, 10)})
              </p>
              <Badge variant={sweep.holdout_valid ? "success" : "danger"} dot>
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
              onClick={onValidateHoldout}
              disabled={isValidatePending || !displayTrial}
              className="btn-secondary"
            >
              {isValidatePending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ShieldCheck className="h-4 w-4" />
              )}
              Validate Holdout
            </button>
          ) : null}
          <button
            type="button"
            onClick={onApply}
            disabled={
              isApplyPending || sweep.status !== "completed" || !displayTrial
            }
            className="btn-primary"
          >
            {isApplyPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <PlayCircle className="h-4 w-4" />
            )}
            {sweep.best_valid ? "Apply best config" : "Apply candidate config"}
          </button>
        </div>
        {validateError ? (
          <p className="text-sm text-danger">
            {validateError.message || "Holdout validation failed to start"}
          </p>
        ) : null}
        {applyData?.revision_id ? (
          <p className="text-sm text-[var(--success)]">
            Applied ({applyData.applied_from ?? "best"}) — revision{" "}
            {applyData.revision_id}
          </p>
        ) : null}
        {applyError ? (
          <p className="text-sm text-danger">
            {applyError.message || "Apply failed"}
          </p>
        ) : null}
      </div>
    </Card>
  );
}
