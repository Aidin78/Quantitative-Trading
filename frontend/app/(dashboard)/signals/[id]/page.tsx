"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Badge, Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function SignalDetailPage() {
  const params = useParams();
  const id = String(params.id);

  const { data, isLoading, error } = useQuery({
    queryKey: ["signal", id],
    queryFn: () => api.signal(id),
  });

  if (isLoading) return <p className="text-muted">Loading...</p>;
  if (error || !data) return <p className="text-danger">Signal not found</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/signals" className="text-sm text-accent hover:underline">
          ← Back to signals
        </Link>
        <h1 className="text-2xl font-semibold">Signal {id}</h1>
        <Badge variant="success">{data.side}</Badge>
      </div>

      <Card title="Final Signal">
        <pre className="overflow-auto text-xs">
          {JSON.stringify(data.final_signal, null, 2)}
        </pre>
      </Card>

      <Card title="Decision Log">
        <p className="mb-2 text-sm text-muted">{data.explainability.summary}</p>
        <pre className="overflow-auto text-xs">
          {JSON.stringify(data.decision_log, null, 2)}
        </pre>
      </Card>

      <Card title="Provider Votes">
        <div className="space-y-2">
          {data.provider_signals.map((s, i) => (
            <div key={i} className="rounded bg-background p-2 text-sm">
              {String(s.provider_id)}: {String(s.side)} ({String(s.confidence)})
            </div>
          ))}
        </div>
      </Card>

      <a
        href={`/replay?correlation_id=${data.correlation_id}`}
        className="text-sm text-accent hover:underline"
      >
        View replay timeline
      </a>
    </div>
  );
}
