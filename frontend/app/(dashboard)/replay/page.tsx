"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { GitBranch, Loader2, Search } from "lucide-react";
import { Suspense, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

function ReplayContent() {
  const params = useSearchParams();
  const [correlationId, setCorrelationId] = useState(
    params.get("correlation_id") ?? "",
  );
  const [mode, setMode] = useState<"strict" | "re_execute">("strict");
  const [revisionId, setRevisionId] = useState("");

  const { data, refetch, isFetching, isSuccess } = useQuery({
    queryKey: ["replay", correlationId, mode, revisionId],
    queryFn: () =>
      api.replay(correlationId, {
        mode,
        revision_id: revisionId || undefined,
      }),
    enabled: false,
  });

  return (
    <div className="page-container">
      <PageHeader
        title="Forensic Replay"
        description="Inspect event chains or re-execute decisions with a different engine revision."
      />

      <Card
        title="Cycle Search"
        subtitle="Enter a correlation_id from a decision"
      >
        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              className="input-field flex-1 font-mono text-sm"
              value={correlationId}
              onChange={(e) => setCorrelationId(e.target.value)}
              placeholder="cycle_btc_1h_..."
            />
            <button
              type="button"
              onClick={() => refetch()}
              disabled={!correlationId || isFetching}
              className="btn-primary shrink-0"
            >
              {isFetching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              Load Timeline
            </button>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="text-xs font-medium uppercase tracking-wider text-muted">
                Mode
              </label>
              <select
                className="input-field mt-2"
                value={mode}
                onChange={(e) =>
                  setMode(e.target.value as "strict" | "re_execute")
                }
              >
                <option value="strict">Strict replay</option>
                <option value="re_execute">Re-execute</option>
              </select>
            </div>
            {mode === "re_execute" ? (
              <div>
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  Revision ID (optional)
                </label>
                <input
                  className="input-field mt-2 font-mono text-sm"
                  value={revisionId}
                  onChange={(e) => setRevisionId(e.target.value)}
                  placeholder="rev_..."
                />
              </div>
            ) : null}
          </div>
        </div>
      </Card>

      {isSuccess && data?.decision_diff ? (
        <Card title="Decision Diff" subtitle="Original vs re-executed">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-[var(--border)] p-4">
              <p className="text-xs font-semibold uppercase text-muted">
                Original
              </p>
              <p className="mt-2 text-sm">
                {data.decision_diff.original.result}
                {data.decision_diff.original.side
                  ? ` · ${data.decision_diff.original.side}`
                  : ""}
              </p>
              {data.decision_diff.original.rejection_reason ? (
                <p className="mt-1 text-xs text-danger">
                  {data.decision_diff.original.rejection_reason}
                </p>
              ) : null}
            </div>
            <div className="rounded-lg border border-[var(--border)] p-4">
              <p className="text-xs font-semibold uppercase text-muted">
                Re-executed
              </p>
              <p className="mt-2 text-sm">
                {data.decision_diff.reexecuted.result}
                {data.decision_diff.reexecuted.side
                  ? ` · ${data.decision_diff.reexecuted.side}`
                  : ""}
              </p>
              {data.decision_diff.reexecuted.rejection_reason ? (
                <p className="mt-1 text-xs text-danger">
                  {data.decision_diff.reexecuted.rejection_reason}
                </p>
              ) : null}
            </div>
          </div>
          <div className="mt-4">
            <Badge variant={data.decision_diff.changed ? "warning" : "success"}>
              {data.decision_diff.changed ? "Decision changed" : "No change"}
            </Badge>
          </div>
        </Card>
      ) : null}

      {isSuccess && data?.timeline && (
        <Card
          title="Event Timeline"
          subtitle={`${data.timeline.length} events · ${data.mode}`}
          className="animate-fade-in"
        >
          {data.timeline.length === 0 ? (
            <EmptyState message="No events found for this cycle" />
          ) : (
            <div className="relative space-y-0">
              <div className="absolute bottom-4 left-[1.125rem] top-4 w-px bg-[var(--border)]" />
              {data.timeline.map((entry, i) => (
                <div key={i} className="relative flex gap-4 pb-6 last:pb-0">
                  <div className="relative z-10 mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--border-strong)] bg-[var(--background-elevated)]">
                    <GitBranch className="h-3.5 w-3.5 text-accent" />
                  </div>
                  <div className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="accent">{String(entry.event_type)}</Badge>
                      {entry.event_family ? (
                        <span className="text-xs text-muted">
                          {entry.event_family}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 font-mono text-xs text-muted">
                      {String(entry.event_time ?? "")}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

export default function ReplayPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center p-12">
          <Loader2 className="h-6 w-6 animate-spin text-accent" />
        </div>
      }
    >
      <ReplayContent />
    </Suspense>
  );
}
