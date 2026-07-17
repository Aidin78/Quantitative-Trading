"use client";

import { GitBranch } from "lucide-react";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import type { ReplayResult } from "@/lib/api";

type Props = {
  data: ReplayResult;
};

export function ReplayTimelineCard({ data }: Props) {
  return (
    <Card
      title="Event Timeline"
      subtitle={`${data.timeline.length} events · ${data.mode} · ${data.correlation_id}`}
      className="animate-fade-in"
    >
      {data.timeline.length === 0 ? (
        <EmptyState message="No events found for this cycle" />
      ) : (
        <div className="relative space-y-0">
          <div className="absolute bottom-4 left-[1.125rem] top-4 w-px bg-[var(--border)]" />
          {data.timeline.map((entry, i) => (
            <div
              key={entry.event_id ?? i}
              className="relative flex gap-4 pb-6 last:pb-0"
            >
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
                {entry.summary ? (
                  <p className="mt-1 text-sm text-foreground/90">
                    {entry.summary}
                  </p>
                ) : null}
                <p className="mt-1 font-mono text-xs text-muted">
                  {String(entry.event_time ?? "")}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
