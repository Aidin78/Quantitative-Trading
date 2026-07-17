"use client";

import { Loader2, PlayCircle } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { DateRangeFields } from "@/components/ui/DateRangeFields";
import { FieldLabel } from "@/components/ui/FieldLabel";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";

type Props = {
  symbol: string;
  onSymbolChange: (value: string) => void;
  startDate: string;
  endDate: string;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  initialCapital: number;
  onInitialCapitalChange: (value: number) => void;
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
  runError,
  walkForwardError,
  isRunPending,
  isJobActive,
  onRun,
}: Props) {
  return (
    <Card
      title="Run Configuration"
      subtitle="Historical validation with live exchange data"
    >
      <div className="space-y-4">
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
