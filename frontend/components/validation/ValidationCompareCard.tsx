"use client";

import { Badge, Card } from "@/components/ui/Card";
import { FieldLabel } from "@/components/ui/FieldLabel";
import type {
  ValidationCompareResponse,
  ValidationRunSummary,
} from "@/lib/api";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";

type Props = {
  historyItems: ValidationRunSummary[];
  compareRunA: string;
  compareRunB: string;
  onCompareRunAChange: (value: string) => void;
  onCompareRunBChange: (value: string) => void;
  compareData: ValidationCompareResponse | undefined;
};

export function ValidationCompareCard({
  historyItems,
  compareRunA,
  compareRunB,
  onCompareRunAChange,
  onCompareRunBChange,
  compareData,
}: Props) {
  return (
    <Card title="Compare Runs" subtitle="Side-by-side metrics for two runs">
      <div className="mb-4 grid gap-4 sm:grid-cols-2">
        <div>
          <FieldLabel label="Run A" tooltip={FORM_TOOLTIPS.compareRunA} />
          <select
            className="input-field mt-2"
            value={compareRunA}
            onChange={(e) => onCompareRunAChange(e.target.value)}
          >
            <option value="">Select run…</option>
            {historyItems.map((row) => (
              <option key={`a-${row.run_id}`} value={row.run_id}>
                {row.start?.slice(0, 10)} → {row.end?.slice(0, 10)} (score{" "}
                {row.score.toFixed(1)})
              </option>
            ))}
          </select>
        </div>
        <div>
          <FieldLabel label="Run B" tooltip={FORM_TOOLTIPS.compareRunB} />
          <select
            className="input-field mt-2"
            value={compareRunB}
            onChange={(e) => onCompareRunBChange(e.target.value)}
          >
            <option value="">Select run…</option>
            {historyItems.map((row) => (
              <option key={`b-${row.run_id}`} value={row.run_id}>
                {row.start?.slice(0, 10)} → {row.end?.slice(0, 10)} (score{" "}
                {row.score.toFixed(1)})
              </option>
            ))}
          </select>
        </div>
      </div>

      {compareRunA && compareRunB && compareRunA === compareRunB ? (
        <p className="text-sm text-muted">Select two different runs.</p>
      ) : null}

      {compareData ? (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Badge
              variant={
                compareData.overall_winner === "tie" ? "accent" : "success"
              }
            >
              Overall winner: {compareData.overall_winner.toUpperCase()}
            </Badge>
            {compareData.revision_diff?.same_revision === false ? (
              <span className="text-xs text-muted">
                Different config revisions
              </span>
            ) : null}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
                  <th className="pb-2 pr-3">Metric</th>
                  <th className="pb-2 pr-3">Run A</th>
                  <th className="pb-2 pr-3">Run B</th>
                  <th className="pb-2 pr-3">Delta</th>
                  <th className="pb-2">Winner</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(compareData.metrics).map(([key, metric]) => (
                  <tr key={key} className="border-b border-[var(--border)]/50">
                    <td className="py-2 pr-3">{key.replace(/_/g, " ")}</td>
                    <td className="py-2 pr-3 font-mono text-xs">
                      {typeof metric.a === "number"
                        ? metric.a.toFixed(2)
                        : metric.a}
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs">
                      {typeof metric.b === "number"
                        ? metric.b.toFixed(2)
                        : metric.b}
                    </td>
                    <td
                      className={`py-2 pr-3 font-mono text-xs ${metric.delta >= 0 ? "text-[var(--success)]" : "text-danger"}`}
                    >
                      {metric.delta >= 0 ? "+" : ""}
                      {metric.delta.toFixed(2)}
                    </td>
                    <td className="py-2 text-xs uppercase">{metric.winner}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </Card>
  );
}
