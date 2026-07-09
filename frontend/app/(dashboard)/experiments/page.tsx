"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Loader2, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function ExperimentsPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["experiments"],
    queryFn: () => api.experiments(),
  });

  const items = data?.items ?? [];
  const allSelected = items.length > 0 && selected.size === items.length;
  const someSelected = selected.size > 0;

  const selectedIds = useMemo(() => Array.from(selected), [selected]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["experiments"] });
    setSelected(new Set());
  };

  const deleteOne = useMutation({
    mutationFn: (id: string) => api.deleteExperiment(id),
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (err) => {
      setActionError(err instanceof Error ? err.message : "Delete failed");
    },
  });

  const deleteMany = useMutation({
    mutationFn: (ids: string[]) => api.deleteExperiments(ids),
    onSuccess: (result) => {
      setActionError(null);
      if (result.blocked.length) {
        setActionError(
          `Deleted ${result.deleted_count}. Skipped active experiment: ${result.blocked.join(", ")}`,
        );
      }
      invalidate();
    },
    onError: (err) => {
      setActionError(err instanceof Error ? err.message : "Bulk delete failed");
    },
  });

  const isDeleting = deleteOne.isPending || deleteMany.isPending;

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set());
      return;
    }
    setSelected(new Set(items.map((exp) => exp.experiment_id)));
  }

  function confirmDeleteOne(id: string, name: string) {
    if (
      !window.confirm(
        `Delete experiment "${name}"? This removes it from the registry. Historical runs and events are kept.`,
      )
    ) {
      return;
    }
    deleteOne.mutate(id);
  }

  function confirmDeleteSelected() {
    if (!selectedIds.length) return;
    if (
      !window.confirm(
        `Delete ${selectedIds.length} selected experiment(s)? This cannot be undone.`,
      )
    ) {
      return;
    }
    deleteMany.mutate(selectedIds);
  }

  return (
    <div className="page-container">
      <PageHeader
        title="Experiments"
        description="Tracked validation and live runs bound to config revisions."
      />

      <Card title="Experiment Registry" subtitle="Governance-bound runs">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-accent" />
          </div>
        ) : !items.length ? (
          <EmptyState
            message="No experiments yet"
            hint="Run validation from the dashboard to create one automatically"
          />
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = someSelected && !allSelected;
                  }}
                  onChange={toggleAll}
                  disabled={isDeleting}
                />
                Select all
              </label>
              {someSelected ? (
                <button
                  type="button"
                  onClick={confirmDeleteSelected}
                  disabled={isDeleting}
                  className="btn-secondary border-danger/30 text-danger hover:border-danger/50"
                >
                  {deleteMany.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  Delete selected ({selected.size})
                </button>
              ) : null}
            </div>

            {actionError ? (
              <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                {actionError}
              </p>
            ) : null}

            <div className="space-y-3">
              {items.map((exp) => {
                const checked = selected.has(exp.experiment_id);
                return (
                  <div
                    key={exp.experiment_id}
                    className={`rounded-lg border bg-[var(--background-elevated)]/50 p-4 transition-colors ${
                      checked ? "border-accent/40" : "border-[var(--border)]"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex min-w-0 flex-1 items-start gap-3">
                        <input
                          type="checkbox"
                          className="mt-1 shrink-0"
                          checked={checked}
                          onChange={() => toggleOne(exp.experiment_id)}
                          disabled={isDeleting}
                          aria-label={`Select ${exp.name}`}
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <FlaskConical className="h-4 w-4 shrink-0 text-accent" />
                            <p className="font-medium text-foreground">
                              {exp.name}
                            </p>
                            <Badge variant="accent">{exp.status}</Badge>
                          </div>
                          <div className="mt-3 grid gap-2 text-xs text-muted sm:grid-cols-2">
                            <p>
                              <span className="text-foreground/70">ID:</span>{" "}
                              <span className="font-mono">
                                {exp.experiment_id}
                              </span>
                            </p>
                            <p>
                              <span className="text-foreground/70">
                                Revision:
                              </span>{" "}
                              <span className="font-mono">
                                {exp.revision_id}
                              </span>
                            </p>
                            <p>
                              <span className="text-foreground/70">Mode:</span>{" "}
                              {exp.mode}
                            </p>
                            <p>
                              <span className="text-foreground/70">
                                Symbols:
                              </span>{" "}
                              {exp.symbols.join(", ")}
                            </p>
                          </div>
                          {exp.hypothesis ? (
                            <p className="mt-2 text-sm text-foreground/80">
                              {exp.hypothesis}
                            </p>
                          ) : null}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          confirmDeleteOne(exp.experiment_id, exp.name)
                        }
                        disabled={isDeleting}
                        className="btn-secondary shrink-0 border-danger/30 px-3 py-2 text-danger hover:border-danger/50"
                        aria-label={`Delete ${exp.name}`}
                      >
                        {deleteOne.isPending &&
                        deleteOne.variables === exp.experiment_id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
