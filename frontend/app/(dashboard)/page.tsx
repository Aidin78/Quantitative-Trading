"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle2,
  Download,
  Layers,
  Loader2,
  TrendingUp,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { DecisionFiltersBar } from "@/components/dashboard/DecisionFilters";
import { LiveStatusCard } from "@/components/dashboard/LiveStatusCard";
import { Badge, Card, EmptyState, StatCard } from "@/components/ui/Card";
import { useDecisionWebSocket } from "@/hooks/useDecisionWebSocket";
import {
  api,
  DecisionSummary,
  type DecisionFilters,
  type EngineStats,
} from "@/lib/api";

export default function DecisionMonitorPage() {
  const [selected, setSelected] = useState<DecisionSummary | null>(null);
  const [filters, setFilters] = useState<DecisionFilters>({ limit: 50 });
  const [exporting, setExporting] = useState(false);
  useDecisionWebSocket();

  const { data: stats } = useQuery({
    queryKey: ["engine-stats"],
    queryFn: () => api.stats(),
    refetchInterval: 30_000,
  });

  const { data: providers } = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.providers(),
  });

  const { data: decisions } = useQuery({
    queryKey: ["decisions", filters],
    queryFn: () => api.decisions(filters),
    refetchInterval: 30_000,
  });

  const { data: detail } = useQuery({
    queryKey: ["decision", selected?.id],
    queryFn: () => api.decision(selected!.id),
    enabled: !!selected,
  });

  const rejectionTotal = stats
    ? Object.values(stats.rejection_breakdown).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="page-container">
      <PageHeader
        title="Decision Monitor"
        description="Real-time view of engine decisions — approvals, rejections, and provider consensus."
        action={
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-secondary text-xs"
              disabled={exporting}
              onClick={async () => {
                setExporting(true);
                try {
                  await api.exportDecisions();
                } finally {
                  setExporting(false);
                }
              }}
            >
              {exporting ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Download className="h-3 w-3" />
              )}
              Export CSV
            </button>
            <Badge variant="accent" dot>
              Monitor
            </Badge>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Total Decisions"
              value={stats?.decisions_today ?? "—"}
              icon={<Activity className="h-4 w-4" />}
            />
            <StatCard
              label="Approval Rate"
              value={stats ? `${(stats.approval_rate * 100).toFixed(1)}` : "—"}
              suffix="%"
              trend={stats && stats.approval_rate > 0.15 ? "up" : "neutral"}
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <StatCard
              label="Rejections"
              value={rejectionTotal}
              trend={rejectionTotal > 0 ? "down" : "neutral"}
              icon={<XCircle className="h-4 w-4" />}
            />
            <StatCard
              label="Active Providers"
              value={stats?.active_providers ?? "—"}
              icon={<Layers className="h-4 w-4" />}
            />
          </div>
        </div>
        <LiveStatusCard />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <Card
          title="Decision Feed"
          subtitle={
            decisions
              ? `${decisions.items.length} of ${decisions.total} decisions`
              : "Click a row to inspect provider votes"
          }
          className="xl:col-span-3"
        >
          <DecisionFiltersBar
            filters={filters}
            providers={(providers?.items ?? []).map((p) => p.provider_id)}
            onChange={setFilters}
          />
          <div className="max-h-[28rem] space-y-2 overflow-y-auto pr-1">
            {decisions?.items.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => setSelected(d)}
                className={`w-full rounded-lg border p-4 text-left transition-all ${
                  selected?.id === d.id
                    ? "border-accent/40 bg-[var(--accent-dim)] shadow-[0_0_20px_var(--glow)]"
                    : "border-[var(--border)] bg-[var(--background-elevated)]/50 hover:border-[var(--border-strong)] hover:bg-[var(--card-hover)]"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex h-9 w-9 items-center justify-center rounded-lg ${
                        d.result === "approved"
                          ? "bg-[var(--success-dim)] text-success"
                          : "bg-[var(--danger-dim)] text-danger"
                      }`}
                    >
                      {d.result === "approved" ? (
                        <CheckCircle2 className="h-4 w-4" />
                      ) : (
                        <XCircle className="h-4 w-4" />
                      )}
                    </div>
                    <div>
                      <p className="font-medium text-foreground">{d.symbol}</p>
                      <p className="text-xs text-muted">{d.timeframe}</p>
                    </div>
                  </div>
                  <Badge
                    variant={d.result === "approved" ? "success" : "danger"}
                  >
                    {d.result}
                  </Badge>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
                  <span>{d.side ?? d.rejection_reason ?? "—"}</span>
                  <span className="text-[var(--border-strong)]">·</span>
                  <span>{new Date(d.timestamp).toLocaleString()}</span>
                  {d.rejection_stage ? (
                    <>
                      <span className="text-[var(--border-strong)]">·</span>
                      <span className="text-danger">{d.rejection_stage}</span>
                    </>
                  ) : null}
                </div>
              </button>
            ))}
            {!decisions?.items.length && (
              <EmptyState
                message="No decisions recorded yet"
                hint="Run a validation job to populate the feed"
              />
            )}
          </div>
        </Card>

        <Card
          title="Rejection Breakdown"
          subtitle="Why the engine says no"
          className="xl:col-span-2"
        >
          <Breakdown stats={stats} />
        </Card>
      </div>

      {detail && (
        <Card
          title="Explainability"
          subtitle={`Decision ${detail.id}`}
          className="animate-fade-in"
        >
          <p className="mb-4 rounded-lg bg-[var(--background-elevated)] px-4 py-3 text-sm leading-relaxed text-foreground/90">
            {detail.explainability.summary}
          </p>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                Provider Votes
              </p>
              <div className="space-y-2">
                {detail.provider_signals.map((s, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] px-3 py-2.5"
                  >
                    <span className="text-sm font-medium">
                      {String(s.provider_id)}
                    </span>
                    <Badge
                      variant={
                        String(s.side) === "BUY"
                          ? "success"
                          : String(s.side) === "SELL"
                            ? "danger"
                            : "default"
                      }
                    >
                      {String(s.side)} · {Number(s.confidence).toFixed(2)}
                    </Badge>
                  </div>
                ))}
                {!detail.provider_signals.length && (
                  <p className="text-sm text-muted">No provider opinions</p>
                )}
              </div>
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                Outcome
              </p>
              {detail.rejection_reason ? (
                <div className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-4">
                  <p className="text-sm font-medium text-danger">Rejected</p>
                  <p className="mt-1 text-sm text-foreground/80">
                    {detail.rejection_reason}
                  </p>
                  {detail.rejection_stage ? (
                    <p className="mt-2 text-xs text-muted">
                      Stage: {detail.rejection_stage}
                    </p>
                  ) : null}
                </div>
              ) : (
                <div className="rounded-lg border border-success/20 bg-[var(--success-dim)] p-4">
                  <p className="text-sm font-medium text-success">Approved</p>
                  <p className="mt-1 text-sm text-foreground/80">
                    {detail.side} with{" "}
                    {(Number(detail.confidence) * 100).toFixed(0)}% confidence
                  </p>
                </div>
              )}
              <Link
                href={`/replay?correlation_id=${detail.correlation_id}`}
                className="btn-secondary mt-4 w-full"
              >
                View replay timeline
              </Link>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

function Breakdown({ stats }: { stats?: EngineStats }) {
  if (
    !stats?.rejection_breakdown ||
    !Object.keys(stats.rejection_breakdown).length
  ) {
    return (
      <EmptyState
        message="No rejection data yet"
        hint="Rejections appear after validation runs"
      />
    );
  }
  const max = Math.max(...Object.values(stats.rejection_breakdown));
  const total = Object.values(stats.rejection_breakdown).reduce(
    (a, b) => a + b,
    0,
  );

  return (
    <div className="space-y-4">
      {Object.entries(stats.rejection_breakdown)
        .sort(([, a], [, b]) => b - a)
        .map(([reason, count]) => {
          const pct = total ? ((count / total) * 100).toFixed(0) : "0";
          return (
            <div key={reason}>
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-medium text-foreground">{reason}</span>
                <span className="text-muted">
                  {count} <span className="text-xs">({pct}%)</span>
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[var(--background-elevated)]">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-danger/80 to-danger/40 transition-all duration-500"
                  style={{ width: `${(count / max) * 100}%` }}
                />
              </div>
            </div>
          );
        })}
    </div>
  );
}
