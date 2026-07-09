"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, GitBranch, Loader2, Search } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { FieldLabel } from "@/components/ui/FieldLabel";
import { api, type CausalGraph, type TimelineEntry } from "@/lib/api";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";

function buildGraphTree(
  graph: CausalGraph | undefined,
  timeline: TimelineEntry[],
): Array<{ node: CausalGraph["nodes"][0]; depth: number }> {
  if (!graph?.nodes.length) {
    return timeline.map((e, i) => ({
      node: {
        id: e.event_id ?? `t-${i}`,
        event_type: String(e.event_type),
        event_family: String(e.event_family ?? ""),
        event_time: String(e.event_time),
      },
      depth: i,
    }));
  }
  const children: Record<string, string[]> = {};
  for (const edge of graph.edges) {
    children[edge.from] = children[edge.from] ?? [];
    children[edge.from].push(edge.to);
  }
  const byId = Object.fromEntries(graph.nodes.map((n) => [n.id, n]));
  const visited = new Set<string>();
  const result: Array<{ node: CausalGraph["nodes"][0]; depth: number }> = [];

  function walk(id: string, depth: number) {
    if (visited.has(id)) return;
    visited.add(id);
    const node = byId[id];
    if (node) result.push({ node, depth });
    for (const child of children[id] ?? []) {
      walk(child, depth + 1);
    }
  }

  const roots = graph.roots.length ? graph.roots : graph.nodes.map((n) => n.id);
  for (const root of roots) {
    walk(root, 0);
  }
  for (const node of graph.nodes) {
    if (!visited.has(node.id)) {
      result.push({ node, depth: 0 });
    }
  }
  return result;
}

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

  const graphTree = useMemo(
    () => buildGraphTree(data?.causal_graph, data?.timeline ?? []),
    [data?.causal_graph, data?.timeline],
  );

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
          <FieldLabel
            label="Correlation ID"
            tooltip={FORM_TOOLTIPS.correlationId}
          />
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
              <FieldLabel label="Mode" tooltip={FORM_TOOLTIPS.replayMode} />
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
                <FieldLabel
                  label="Revision ID (optional)"
                  tooltip={FORM_TOOLTIPS.revisionId}
                />
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

      {isSuccess && data?.feature_drift?.detected ? (
        <div className="flex items-start gap-3 rounded-lg border border-warning/30 bg-[var(--warning-dim)] p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
          <div>
            <p className="font-medium text-warning">Feature drift detected</p>
            <p className="mt-1 text-sm text-muted">
              {data.feature_drift.reason ??
                "Stored features differ from current config."}
            </p>
            {data.feature_drift.drifted_features?.length ? (
              <p className="mt-2 font-mono text-xs text-muted">
                {data.feature_drift.drifted_features.join(", ")}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

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

      {isSuccess && graphTree.length > 0 ? (
        <Card title="Causal Graph" subtitle="Event causation chain">
          <div className="space-y-1">
            {graphTree.map(({ node, depth }) => (
              <div
                key={node.id}
                className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 py-2 pr-3"
                style={{ marginLeft: `${depth * 1.5}rem` }}
              >
                <div className="ml-3 h-full w-px bg-accent/40" />
                <GitBranch className="h-3.5 w-3.5 shrink-0 text-accent" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="accent">{node.event_type}</Badge>
                    <span className="text-xs text-muted">
                      {node.event_family}
                    </span>
                  </div>
                  <p className="font-mono text-xs text-muted">
                    {node.event_time}
                  </p>
                </div>
              </div>
            ))}
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
