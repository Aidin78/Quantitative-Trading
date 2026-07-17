"use client";

import { Loader2, PlayCircle } from "lucide-react";
import { Badge, Card } from "@/components/ui/Card";
import { FieldLabel } from "@/components/ui/FieldLabel";
import type { WalkForwardResult } from "@/lib/api";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";

type Props = {
  wfWindows: number;
  onWfWindowsChange: (value: number) => void;
  wfTrainRatio: number;
  onWfTrainRatioChange: (value: number) => void;
  isPending: boolean;
  onRun: () => void;
  result: WalkForwardResult | undefined;
};

export function ValidationWalkForwardCard({
  wfWindows,
  onWfWindowsChange,
  wfTrainRatio,
  onWfTrainRatioChange,
  isPending,
  onRun,
  result,
}: Props) {
  return (
    <Card title="Walk-Forward" subtitle="Rolling window validation">
      <div className="mb-4 grid gap-4 sm:grid-cols-2">
        <div>
          <FieldLabel label="Windows" tooltip={FORM_TOOLTIPS.wfWindows} />
          <input
            type="number"
            min={2}
            max={10}
            className="input-field mt-2"
            value={wfWindows}
            onChange={(e) => onWfWindowsChange(Number(e.target.value))}
          />
        </div>
        <div>
          <FieldLabel
            label="Train Ratio"
            tooltip={FORM_TOOLTIPS.wfTrainRatio}
          />
          <input
            type="number"
            min={0.1}
            max={0.9}
            step={0.1}
            className="input-field mt-2"
            value={wfTrainRatio}
            onChange={(e) => onWfTrainRatioChange(Number(e.target.value))}
          />
        </div>
      </div>
      <button
        type="button"
        onClick={onRun}
        disabled={isPending}
        className="btn-primary"
      >
        {isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <PlayCircle className="h-4 w-4" />
        )}
        Run Walk-Forward
      </button>

      {result?.windows.length ? (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
                <th className="pb-2 pr-4">Window</th>
                <th className="pb-2 pr-4">Test Period</th>
                <th className="pb-2 pr-4">Status</th>
                <th className="pb-2">Trades</th>
              </tr>
            </thead>
            <tbody>
              {result.windows.map((w) => (
                <tr
                  key={w.window}
                  className="border-b border-[var(--border)]/50"
                >
                  <td className="py-2 pr-4">{w.window + 1}</td>
                  <td className="py-2 pr-4 font-mono text-xs">
                    {w.test_start.slice(0, 10)} → {w.test_end.slice(0, 10)}
                  </td>
                  <td className="py-2 pr-4">
                    <Badge
                      variant={w.status === "completed" ? "success" : "danger"}
                    >
                      {w.status}
                    </Badge>
                  </td>
                  <td className="py-2">
                    {w.outcome_metrics?.total_trades != null
                      ? String(w.outcome_metrics.total_trades)
                      : w.error
                        ? "—"
                        : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.windows.some((w) => w.error) ? (
            <div className="mt-4 space-y-2">
              {result.windows
                .filter((w) => w.error)
                .map((w) => (
                  <p
                    key={`err-${w.window}`}
                    className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger"
                  >
                    Window {w.window + 1}: {w.error}
                  </p>
                ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
