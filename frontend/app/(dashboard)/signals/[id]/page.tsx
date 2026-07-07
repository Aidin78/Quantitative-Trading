"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { ArrowLeft, GitBranch } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

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
      </div>
    );
  }

  return (
    <div className="page-container">
      <Link
        href="/signals"
        className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-accent"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to signals
      </Link>

      <PageHeader
        title={`Signal ${id}`}
        description={data.explainability.summary}
        action={<Badge variant="success">{data.side}</Badge>}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Final Signal">
          <pre className="overflow-auto rounded-lg bg-[var(--background)] p-4 font-mono text-xs text-muted">
            {JSON.stringify(data.final_signal, null, 2)}
          </pre>
        </Card>

        <Card title="Provider Votes">
          <div className="space-y-2">
            {data.provider_signals.map((s, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] px-3 py-2.5 text-sm"
              >
                <span className="font-medium">{String(s.provider_id)}</span>
                <span className="text-muted">
                  {String(s.side)} ({String(s.confidence)})
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="Decision Log">
        <pre className="max-h-80 overflow-auto rounded-lg bg-[var(--background)] p-4 font-mono text-xs text-muted">
          {JSON.stringify(data.decision_log, null, 2)}
        </pre>
      </Card>

      <Link
        href={`/replay?correlation_id=${data.correlation_id}`}
        className="btn-secondary inline-flex"
      >
        <GitBranch className="h-4 w-4" />
        View replay timeline
      </Link>
    </div>
  );
}
