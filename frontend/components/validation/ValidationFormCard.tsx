"use client";

import { Loader2, PlayCircle } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { DateRangeFields } from "@/components/ui/DateRangeFields";
import { FieldLabel } from "@/components/ui/FieldLabel";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";
import type { ValidationStrategy } from "@/lib/api";

type Props = {
  symbol: string;
  onSymbolChange: (value: string) => void;
  startDate: string;
  endDate: string;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  initialCapital: number;
  onInitialCapitalChange: (value: number) => void;
  strategy: string;
  strategies: ValidationStrategy[];
  onStrategyChange: (value: string) => void;
  runError: Error | null;
  walkForwardError: Error | null;
  isRunPending: boolean;
  isJobActive: boolean;
  onRun: () => void;
};

export function ValidationFormCard({
  symbol,
  onSymbolChange,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  initialCapital,
  onInitialCapitalChange,
  strategy,
  strategies,
  onStrategyChange,
  runError,
  walkForwardError,
  isRunPending,
  isJobActive,
  onRun,
}: Props) {
  const active = strategies.find((s) => s.key === strategy);

  return (
    <Card
      title="Run Configuration"
      subtitle="Historical validation with cached exchange data"
    >
      <div className="space-y-4">
        {strategies.length > 0 && (
          <div>
            <FieldLabel
              label="Strategy"
              tooltip="Which configuration to validate. The baseline is a demo engine with no validated edge; the managed long-core is the strategy that passed research."
            />
            <select
              className="input-field mt-2"
              value={strategy}
              onChange={(e) => onStrategyChange(e.target.value)}
            >
              {strategies.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
            {active && (
              <p className="mt-2 text-xs leading-relaxed text-muted">
                {active.summary}{" "}
                <span className="text-foreground/70">
                  Runs on {active.timeframe} bars.
                </span>
              </p>
            )}
          </div>
        )}
        <div>
          <FieldLabel label="Symbol" tooltip={FORM_TOOLTIPS.symbol} />
          <input
            className="input-field mt-2"
            value={symbol}
            onChange={(e) => onSymbolChange(e.target.value)}
          />
        </div>
        <DateRangeFields
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={onStartDateChange}
          onEndDateChange={onEndDateChange}
        />
        <div>
          <FieldLabel
            label="Initial Capital"
            tooltip={FORM_TOOLTIPS.initialCapital}
          />
          <input
            type="number"
            min={100}
            step={100}
            className="input-field mt-2"
            value={initialCapital}
            onChange={(e) => onInitialCapitalChange(Number(e.target.value))}
          />
        </div>
        {(runError || walkForwardError) && (
          <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
            {runError?.message ||
              walkForwardError?.message ||
              "Validation request failed"}
          </p>
        )}
        <button
          type="button"
          onClick={onRun}
          disabled={isRunPending || isJobActive}
          className="btn-primary w-full"
        >
          {isRunPending || isJobActive ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <PlayCircle className="h-4 w-4" />
          )}
          {isJobActive ? "Validation running…" : "Run Validation"}
        </button>
      </div>
    </Card>
  );
}
