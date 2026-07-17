"use client";

import { ValidationMetricsPanel } from "@/components/validation/ValidationMetricsPanel";
import { Card } from "@/components/ui/Card";
import type { ValidationTrade } from "@/lib/api";

type Props = {
  engine: Record<string, unknown>;
  outcome?: Record<string, unknown> | null;
  trades?: ValidationTrade[];
};

export function ValidationResultsCard({ engine, outcome, trades }: Props) {
  return (
    <Card title="Validation Results" subtitle="Engine and outcome metrics">
      <ValidationMetricsPanel
        engine={engine}
        outcome={outcome ?? undefined}
        trades={trades}
      />
    </Card>
  );
}
