"use client";

import { Loader2, Trash2 } from "lucide-react";
import { Card, EmptyState } from "@/components/ui/Card";
import type { ValidationRunSummary } from "@/lib/api";

type Props = {
  historyItems: ValidationRunSummary[];
  selectedRuns: Set<string>;
  allHistorySelected: boolean;
  someHistorySelected: boolean;
  historyError: string | null;
  isDeletingHistory: boolean;
  deletingRunId: string | undefined;
  isBulkDeletePending: boolean;
  onToggleRunSelection: (runId: string) => void;
  onToggleAllHistory: () => void;
  onConfirmDeleteRun: (runId: string) => void;
  onConfirmDeleteSelectedRuns: () => void;
  onViewRun: (runId: string) => void;
};

export function ValidationHistoryCard({
  historyItems,
  selectedRuns,
  allHistorySelected,
  someHistorySelected,
  historyError,
  isDeletingHistory,
  deletingRunId,
  isBulkDeletePending,
  onToggleRunSelection,
  onToggleAllHistory,
  onConfirmDeleteRun,
  onConfirmDeleteSelectedRuns,
  onViewRun,
}: Props) {
  return (
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
                onChange={onToggleAllHistory}
                disabled={isDeletingHistory}
              />
              Select all
            </label>
            {someHistorySelected ? (
              <button
                type="button"
                onClick={onConfirmDeleteSelectedRuns}
                disabled={isDeletingHistory}
                className="btn-secondary border-danger/30 text-danger hover:border-danger/50"
              >
                {isBulkDeletePending ? (
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
                  <th className="w-8 pb-2 pr-2" />
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
                        onChange={() => onToggleRunSelection(row.run_id)}
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
                          onClick={() => onViewRun(row.run_id)}
                        >
                          View
                        </button>
                        <button
                          type="button"
                          className="btn-secondary border-danger/30 px-2 py-1 text-xs text-danger hover:border-danger/50"
                          onClick={() => onConfirmDeleteRun(row.run_id)}
                          disabled={isDeletingHistory}
                          aria-label={`Delete run ${row.run_id}`}
                        >
                          {deletingRunId === row.run_id ? (
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
  );
}
