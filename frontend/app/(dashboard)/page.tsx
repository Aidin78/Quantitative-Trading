"use client";

import { useQuery } from "@tanstack/react-query";
import { useDecisionWebSocket } from "@/hooks/useDecisionWebSocket";
import { useState } from "react";
import { Badge, Card } from "@/components/ui/Card";
import { api, DecisionSummary, type EngineStats } from "@/lib/api";

export default function DecisionMonitorPage() {
  const [selected, setSelected] = useState<DecisionSummary | null>(null);
  useDecisionWebSocket();

  const { data: stats } = useQuery({
    queryKey: ["engine-stats"],
    queryFn: () => api.stats(),
    refetchInterval: 30_000,
  });

  const { data: decisions } = useQuery({
    queryKey: ["decisions"],
    queryFn: () => api.decisions("limit=50"),
    refetchInterval: 30_000,
  });

  const { data: detail } = useQuery({
    queryKey: ["decision", selected?.id],
    queryFn: () => api.decision(selected!.id),
    enabled: !!selected,
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Decision Monitor</h1>
        <p className="text-sm text-muted">
          Live feed of engine decisions (WebSocket + polling)
        </p>
      </header>

      <StatsRow stats={stats} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Decision Feed">
          <div className="max-h-96 space-y-2 overflow-y-auto">
            {decisions?.items.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => setSelected(d)}
                className={`w-full rounded border border-border p-3 text-left text-sm hover:bg-background ${
                  selected?.id === d.id ? "ring-1 ring-accent" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{d.symbol}</span>
                  <Badge
                    variant={d.result === "approved" ? "success" : "danger"}
                  >
                    {d.result}
                  </Badge>
                </div>
                <div className="mt-1 text-xs text-muted">
                  {d.side ?? d.rejection_reason ?? "—"} ·{" "}
                  {new Date(d.timestamp).toLocaleString()}
                </div>
                {d.rejection_stage && (
                  <div className="mt-1 text-xs text-danger">
                    stage: {d.rejection_stage}
                  </div>
                )}
              </button>
            ))}
            {!decisions?.items.length && (
              <p className="text-sm text-muted">
                No decisions yet. Run validation to seed data.
              </p>
            )}
          </div>
        </Card>

        <Card title="Rejection Breakdown">
          <Breakdown stats={stats} />
        </Card>
      </div>

      {detail && (
        <Card title="Provider Votes & Explainability">
          <p className="mb-3 text-sm">{detail.explainability.summary}</p>
          <div className="space-y-2">
            {detail.provider_signals.map((s, i) => (
              <div key={i} className="rounded bg-background p-2 text-sm">
                <span className="font-medium">{String(s.provider_id)}</span>:{" "}
                {String(s.side)} ({String(s.confidence)})
              </div>
            ))}
          </div>
          {detail.rejection_reason && (
            <p className="mt-3 text-sm text-danger">
              Reason: {detail.rejection_reason}
              {detail.rejection_stage
                ? ` (stage: ${detail.rejection_stage})`
                : ""}
            </p>
          )}
          <a
            href={`/replay?correlation_id=${detail.correlation_id}`}
            className="mt-3 inline-block text-sm text-accent hover:underline"
          >
            View replay timeline
          </a>
        </Card>
      )}
    </div>
  );
}

function StatsRow({ stats }: { stats?: EngineStats }) {
  if (!stats) return null;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Card>
        <div className="text-2xl font-semibold">{stats.decisions_today}</div>
        <div className="text-xs text-muted">Decisions</div>
      </Card>
      <Card>
        <div className="text-2xl font-semibold">
          {(stats.approval_rate * 100).toFixed(1)}%
        </div>
        <div className="text-xs text-muted">Approval Rate</div>
      </Card>
      <Card>
        <div className="text-2xl font-semibold">
          {Object.values(stats.rejection_breakdown).reduce((a, b) => a + b, 0)}
        </div>
        <div className="text-xs text-muted">Rejections</div>
      </Card>
      <Card>
        <div className="text-2xl font-semibold">{stats.active_providers}</div>
        <div className="text-xs text-muted">Active Providers</div>
      </Card>
    </div>
  );
}

function Breakdown({ stats }: { stats?: EngineStats }) {
  if (
    !stats?.rejection_breakdown ||
    !Object.keys(stats.rejection_breakdown).length
  ) {
    return <p className="text-sm text-muted">No rejection data</p>;
  }
  const max = Math.max(...Object.values(stats.rejection_breakdown));
  return (
    <div className="space-y-2">
      {Object.entries(stats.rejection_breakdown).map(([reason, count]) => (
        <div key={reason}>
          <div className="mb-1 flex justify-between text-xs">
            <span>{reason}</span>
            <span>{count}</span>
          </div>
          <div className="h-2 rounded bg-background">
            <div
              className="h-2 rounded bg-danger/70"
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
