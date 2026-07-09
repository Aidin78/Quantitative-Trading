"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, LineChart, Loader2 } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

const PAGE_SIZE = 50;

export default function SignalsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["signals", page],
    queryFn: () => api.signals({ page, limit: PAGE_SIZE }),
    refetchInterval: 30_000,
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="page-container">
      <PageHeader
        title="Signals"
        description="Approved decisions only — the final output of the decision engine."
      />

      <Card
        title="Approved Signals"
        subtitle={
          data
            ? `${data.total} total · page ${data.page} of ${totalPages}`
            : "Loading…"
        }
      >
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-muted">
            <Loader2 className="h-5 w-5 animate-spin text-accent" />
            Loading signals…
          </div>
        ) : isError ? (
          <div className="rounded-lg border border-danger/30 bg-[var(--danger-dim)] p-4">
            <p className="font-medium text-danger">Failed to load signals</p>
            <p className="mt-1 text-sm text-muted">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
            <button
              type="button"
              className="btn-secondary mt-3 text-xs"
              onClick={() => refetch()}
            >
              Retry
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {data?.items.map((s) => (
              <div
                key={s.id}
                className="group flex flex-col gap-3 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-4 transition-all hover:border-accent/30 hover:bg-[var(--accent-dim)] sm:flex-row sm:items-center sm:justify-between"
              >
                <Link
                  href={`/signals/${s.id}`}
                  className="flex min-w-0 flex-1 items-center gap-4"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--success-dim)] text-success">
                    <LineChart className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">{s.symbol}</p>
                    <p className="text-xs text-muted">
                      {new Date(s.timestamp).toLocaleString()}
                    </p>
                  </div>
                </Link>
                <div className="flex items-center gap-2 sm:gap-3">
                  <Badge variant="success">
                    {s.side} {((s.confidence ?? 0) * 100).toFixed(0)}%
                  </Badge>
                  <Link
                    href={`/signals/${s.id}`}
                    className="btn-secondary text-xs"
                  >
                    Details
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            ))}
            {!data?.items.length && (
              <EmptyState
                message="No approved signals yet"
                hint="Run validation or wait for live/paper approvals — only approved decisions appear here"
              />
            )}
            {data && data.total > PAGE_SIZE ? (
              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  className="btn-secondary text-xs"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <span className="text-xs text-muted">
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  className="btn-secondary text-xs"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            ) : null}
          </div>
        )}
      </Card>
    </div>
  );
}
