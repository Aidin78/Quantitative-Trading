"use client";

import { ChevronDown } from "lucide-react";
import { Fragment, useState, type ReactNode } from "react";
import { FieldLabel } from "@/components/ui/FieldLabel";
import { Badge } from "@/components/ui/Card";
import type { OptimizationTrial } from "@/lib/api";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";
import {
  enabledProviderChips,
  fmtParamsWithoutEnabled,
} from "@/lib/optimizationSpaces";

function fmtParams(params: Record<string, number | string>) {
  return fmtParamsWithoutEnabled(params);
}

type Props = {
  trials: OptimizationTrial[];
  topTrialIds: Set<string>;
  topK: number;
};

function MetricCell({
  label,
  tooltip,
  value,
}: {
  label: string;
  tooltip: string;
  value: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--background)]/60 p-3">
      <FieldLabel label={label} tooltip={tooltip} />
      <p className="mt-2 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

export function OptimizationTrialsTable({ trials, topTrialIds, topK }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const sorted = trials
    .slice()
    .sort(
      (a, b) =>
        (b.composite_score ?? b.test_score ?? b.train_score) -
        (a.composite_score ?? a.test_score ?? a.train_score),
    );

  function toggleRow(trialId: string) {
    setExpandedId((prev) => (prev === trialId ? null : trialId));
  }

  return (
    <div className="overflow-x-auto">
      <p className="mb-3 text-xs text-muted">
        Click a row to expand details. Test metrics are only computed for the
        top {topK} train candidates (highlighted).
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
            <th className="pb-2 pr-2 w-8" aria-label="Expand row" />
            <th className="pb-2 pr-3">
              <FieldLabel
                label="Params"
                tooltip={FORM_TOOLTIPS.optTrialParams}
              />
            </th>
            <th className="pb-2 pr-3">
              <FieldLabel label="Train" tooltip={FORM_TOOLTIPS.optTrialTrain} />
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((trial) => {
            const isFinalist = topTrialIds.has(trial.trial_id);
            const hasTest = trial.test_score != null;
            const isExpanded = expandedId === trial.trial_id;
            const compositeLabel =
              trial.composite_score != null
                ? trial.composite_score.toFixed(1)
                : hasTest
                  ? "ineligible"
                  : "—";

            return (
              <Fragment key={trial.trial_id}>
                <tr
                  onClick={() => toggleRow(trial.trial_id)}
                  className={`cursor-pointer border-b border-[var(--border)]/50 transition-colors hover:bg-[var(--background-elevated)]/40 ${
                    isFinalist ? "bg-[var(--accent-dim)]/30" : ""
                  } ${isExpanded ? "border-b-0" : ""}`}
                >
                  <td className="py-2 pr-2">
                    <ChevronDown
                      className={`h-4 w-4 text-muted transition-transform ${
                        isExpanded ? "rotate-180" : ""
                      }`}
                    />
                  </td>
                  <td className="py-2 pr-3 font-mono text-xs">
                    <div className="flex flex-col gap-2">
                      {enabledProviderChips(trial.params).length > 0 ? (
                        <div className="flex flex-wrap items-center gap-1.5">
                          {enabledProviderChips(trial.params).map((chip) => (
                            <Badge key={chip} variant="accent">
                              {chip}
                            </Badge>
                          ))}
                          {trial.params.min_agreeing_providers != null ? (
                            <Badge variant="default">
                              agree ≥
                              {String(trial.params.min_agreeing_providers)}
                            </Badge>
                          ) : null}
                        </div>
                      ) : null}
                      <div className="flex flex-wrap items-center gap-2">
                        <span>{fmtParams(trial.params)}</span>
                        {isFinalist ? (
                          <Badge variant="accent">Top {topK}</Badge>
                        ) : null}
                      </div>
                    </div>
                  </td>
                  <td className="py-2 pr-3 font-medium">
                    {trial.train_score.toFixed(1)}
                  </td>
                </tr>
                {isExpanded ? (
                  <tr
                    className={`border-b border-[var(--border)]/50 ${
                      isFinalist ? "bg-[var(--accent-dim)]/20" : ""
                    }`}
                  >
                    <td colSpan={3} className="px-2 pb-3 pt-0">
                      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-4">
                        {hasTest ? (
                          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                            <MetricCell
                              label="Test"
                              tooltip={FORM_TOOLTIPS.optTrialTest}
                              value={trial.test_score!.toFixed(1)}
                            />
                            <MetricCell
                              label="Return"
                              tooltip={FORM_TOOLTIPS.optTrialReturn}
                              value={
                                trial.test_return_pct != null
                                  ? `${trial.test_return_pct.toFixed(1)}%`
                                  : "—"
                              }
                            />
                            <MetricCell
                              label="Trades"
                              tooltip={FORM_TOOLTIPS.optTrialTrades}
                              value={trial.test_total_trades ?? "—"}
                            />
                            <MetricCell
                              label="Composite"
                              tooltip={FORM_TOOLTIPS.optTrialComposite}
                              value={compositeLabel}
                            />
                            <MetricCell
                              label="Stability"
                              tooltip={FORM_TOOLTIPS.optTrialStability}
                              value={
                                trial.stability != null
                                  ? `${(trial.stability * 100).toFixed(0)}%`
                                  : "—"
                              }
                            />
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <p className="text-xs text-muted">
                              This trial was not re-tested on held-out data.
                              Only train-period metrics are available.
                            </p>
                            <div className="grid gap-3 sm:grid-cols-2">
                              <MetricCell
                                label="Return"
                                tooltip={FORM_TOOLTIPS.optTrialReturn}
                                value={
                                  trial.train_return_pct != null
                                    ? `${trial.train_return_pct.toFixed(1)}% (train)`
                                    : "—"
                                }
                              />
                              <MetricCell
                                label="Trades"
                                tooltip={FORM_TOOLTIPS.optTrialTrades}
                                value={trial.train_total_trades ?? "—"}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
