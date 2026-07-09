"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { ArrowLeft, GitBranch } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

function providerBadgeVariant(side: string) {
  if (side === "BUY") return "success" as const;
  if (side === "SELL") return "danger" as const;
  return "default" as const;
}

export default function SignalDetailPage() {
  const params = useParams();
  const id = String(params.id);

  const { data, isLoading, error } = useQuery({
    queryKey: ["signal", id],
    queryFn: () => api.signal(id),
  });

  if (isLoading) {
    return (
      <div className="page-container">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 rounded-lg bg-[var(--card)]" />
          <div className="h-40 rounded-xl bg-[var(--card)]" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page-container">
        <p className="text-danger">Signal not found</p>
        <Link href="/signals" className="btn-secondary mt-4 inline-flex">
          Back to signals
        </Link>
      </div>
    );
  }

  return (
    <div className="page-container space-y-6">
      <Link
        href="/signals"
        className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-accent"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to signals
      </Link>

      <PageHeader
        title={`${data.symbol} · ${data.side ?? "Signal"}`}
        description={data.explainability.summary}
        action={
          <Badge variant="success">
            {data.side} · {((data.confidence ?? 0) * 100).toFixed(0)}%
          </Badge>
        }
      />

      <Card title="Outcome" subtitle={`Decision ${data.id}`}>
        <div className="rounded-lg border border-success/20 bg-[var(--success-dim)] p-4">
          <p className="text-sm font-medium text-success">Approved</p>
          <p className="mt-1 text-sm text-foreground/80">
            {data.side} with {(Number(data.confidence) * 100).toFixed(0)}%
            confidence on {data.timeframe ?? "1h"}
          </p>
          <p className="mt-2 font-mono text-xs text-muted">
            correlation: {data.correlation_id}
          </p>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Provider Votes">
          <div className="space-y-2">
            {data.provider_signals.map((s, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] px-3 py-2.5"
              >
                <span className="text-sm font-medium">
                  {String(s.provider_id)}
                </span>
                <Badge variant={providerBadgeVariant(String(s.side))}>
                  {String(s.side)} · {Number(s.confidence).toFixed(2)}
                </Badge>
              </div>
            ))}
            {!data.provider_signals.length && (
              <p className="text-sm text-muted">
                No provider opinions recorded
              </p>
            )}
          </div>
        </Card>

        <Card title="Market Context">
          {data.market_context ? (
            <div className="space-y-2 text-sm">
              {Object.entries(data.market_context).map(([key, value]) => (
                <div
                  key={key}
                  className="flex justify-between rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] px-3 py-2"
                >
                  <span className="text-muted">{key}</span>
                  <span className="font-medium">{String(value)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">No market context snapshot</p>
          )}
        </Card>
      </div>

      {data.feature_snapshot ? (
        <Card title="Feature Snapshot">
          <pre className="max-h-64 overflow-auto rounded-lg bg-[var(--background)] p-4 font-mono text-xs text-muted">
            {JSON.stringify(data.feature_snapshot, null, 2)}
          </pre>
        </Card>
      ) : null}

      {data.final_signal ? (
        <Card title="Final Signal">
          <pre className="overflow-auto rounded-lg bg-[var(--background)] p-4 font-mono text-xs text-muted">
            {JSON.stringify(data.final_signal, null, 2)}
          </pre>
        </Card>
      ) : null}

      <Card title="Decision Log">
        <pre className="max-h-80 overflow-auto rounded-lg bg-[var(--background)] p-4 font-mono text-xs text-muted">
          {JSON.stringify(data.decision_log, null, 2)}
        </pre>
      </Card>

      <Link
        href={`/replay?correlation_id=${encodeURIComponent(data.correlation_id)}`}
        className="btn-secondary inline-flex"
      >
        <GitBranch className="h-4 w-4" />
        View replay timeline
      </Link>
    </div>
  );
}
