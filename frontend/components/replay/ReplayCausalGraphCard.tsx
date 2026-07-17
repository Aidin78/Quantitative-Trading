"use client";

import { GitBranch } from "lucide-react";
import { Badge, Card } from "@/components/ui/Card";
import type { CausalGraph } from "@/lib/api";

type Props = {
  graphTree: Array<{ node: CausalGraph["nodes"][0]; depth: number }>;
};

export function ReplayCausalGraphCard({ graphTree }: Props) {
  return (
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
                <span className="text-xs text-muted">{node.event_family}</span>
              </div>
              <p className="font-mono text-xs text-muted">{node.event_time}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
