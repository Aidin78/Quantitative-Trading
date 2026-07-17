"use client";

import { Badge, Card } from "@/components/ui/Card";
import type { DecisionDiff } from "@/lib/api";

type Props = {
  decisionDiff: DecisionDiff;
};

export function ReplayDecisionDiffCard({ decisionDiff }: Props) {
  return (
    <Card title="Decision Diff" subtitle="Original vs re-executed">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-[var(--border)] p-4">
          <p className="text-xs font-semibold uppercase text-muted">Original</p>
          <p className="mt-2 text-sm">
            {decisionDiff.original.result}
            {decisionDiff.original.side
              ? ` · ${decisionDiff.original.side}`
              : ""}
          </p>
          {decisionDiff.original.rejection_reason ? (
            <p className="mt-1 text-xs text-danger">
              {decisionDiff.original.rejection_reason}
            </p>
          ) : null}
        </div>
        <div className="rounded-lg border border-[var(--border)] p-4">
          <p className="text-xs font-semibold uppercase text-muted">
            Re-executed
          </p>
          <p className="mt-2 text-sm">
            {decisionDiff.reexecuted.result}
            {decisionDiff.reexecuted.side
              ? ` · ${decisionDiff.reexecuted.side}`
              : ""}
          </p>
          {decisionDiff.reexecuted.rejection_reason ? (
            <p className="mt-1 text-xs text-danger">
              {decisionDiff.reexecuted.rejection_reason}
            </p>
          ) : null}
        </div>
      </div>
      <div className="mt-4">
        <Badge variant={decisionDiff.changed ? "warning" : "success"}>
          {decisionDiff.changed ? "Decision changed" : "No change"}
        </Badge>
      </div>
    </Card>
  );
}
