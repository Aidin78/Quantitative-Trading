"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, LineChart } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function SignalsPage() {
  const { data } = useQuery({
    queryKey: ["signals"],
    queryFn: () => api.signals(),
  });

  return (
    <div className="page-container">
      <PageHeader
        title="Signals"
        description="Approved decisions only — the final output of the decision engine."
      />

      <Card
        title="Approved Signals"
        subtitle={`${data?.items.length ?? 0} total`}
      >
        <div className="space-y-2">
          {data?.items.map((s) => (
            <Link
              key={s.id}
              href={`/signals/${s.id}`}
              className="group flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-4 transition-all hover:border-accent/30 hover:bg-[var(--accent-dim)]"
            >
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--success-dim)] text-success">
                  <LineChart className="h-5 w-5" />
                </div>
                <div>
                  <p className="font-medium text-foreground">{s.symbol}</p>
                  <p className="text-xs text-muted">
                    {new Date(s.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant="success">
                  {s.side} {((s.confidence ?? 0) * 100).toFixed(0)}%
                </Badge>
                <ArrowRight className="h-4 w-4 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
              </div>
            </Link>
          ))}
          {!data?.items.length && (
            <EmptyState
              message="No approved signals yet"
              hint="Signals appear when the engine approves a decision"
            />
          )}
        </div>
      </Card>
    </div>
  );
}
