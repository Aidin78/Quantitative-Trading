"use client";

import { Database, Loader2 } from "lucide-react";
import { MONTH_PRESETS } from "@/components/market-data/formatBytes";
import { Card } from "@/components/ui/Card";
import { DateRangeFields } from "@/components/ui/DateRangeFields";
import { CheckboxField, FieldLabel } from "@/components/ui/FieldLabel";
import { FORM_TOOLTIPS } from "@/lib/formTooltips";

type Props = {
  symbol: string;
  onSymbolChange: (value: string) => void;
  timeframe: string;
  onTimeframeChange: (value: string) => void;
  useCustomRange: boolean;
  onUseCustomRangeChange: (value: boolean) => void;
  months: number;
  onMonthsChange: (value: number) => void;
  startDate: string;
  endDate: string;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  force: boolean;
  onForceChange: (value: boolean) => void;
  downloadError: unknown;
  lastResult: string | null;
  isPending: boolean;
  onDownload: () => void;
};

export function MarketDataDownloadCard({
  symbol,
  onSymbolChange,
  timeframe,
  onTimeframeChange,
  useCustomRange,
  onUseCustomRangeChange,
  months,
  onMonthsChange,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  force,
  onForceChange,
  downloadError,
  lastResult,
  isPending,
  onDownload,
}: Props) {
  return (
    <Card
      title="Download & Cache"
      subtitle="One request fetches the full range and saves it on the server"
    >
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <FieldLabel label="Symbol" tooltip={FORM_TOOLTIPS.symbol} />
            <input
              className="input-field mt-2"
              value={symbol}
              onChange={(e) => onSymbolChange(e.target.value)}
            />
          </div>
          <div>
            <FieldLabel label="Timeframe" tooltip={FORM_TOOLTIPS.timeframe} />
            <select
              className="input-field mt-2"
              value={timeframe}
              onChange={(e) => onTimeframeChange(e.target.value)}
            >
              <option value="1h">1h</option>
              <option value="4h">4h</option>
            </select>
          </div>
        </div>

        <div>
          <FieldLabel label="Range Mode" tooltip={FORM_TOOLTIPS.rangeMode} />
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              className={`btn-secondary px-2.5 py-1 text-xs ${!useCustomRange ? "ring-1 ring-accent" : ""}`}
              onClick={() => onUseCustomRangeChange(false)}
            >
              Last N months
            </button>
            <button
              type="button"
              className={`btn-secondary px-2.5 py-1 text-xs ${useCustomRange ? "ring-1 ring-accent" : ""}`}
              onClick={() => onUseCustomRangeChange(true)}
            >
              Custom dates
            </button>
          </div>
        </div>

        {!useCustomRange ? (
          <div>
            <FieldLabel label="Period" tooltip={FORM_TOOLTIPS.period} />
            <div className="mt-2 flex flex-wrap gap-2">
              {MONTH_PRESETS.map((preset) => (
                <button
                  key={preset.months}
                  type="button"
                  className={`btn-secondary px-2.5 py-1 text-xs ${months === preset.months ? "ring-1 ring-accent" : ""}`}
                  onClick={() => onMonthsChange(preset.months)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted">
              Downloads from {months} calendar month
              {months > 1 ? "s" : ""} ago through today.
            </p>
          </div>
        ) : (
          <DateRangeFields
            layout="grid"
            startDate={startDate}
            endDate={endDate}
            onStartDateChange={onStartDateChange}
            onEndDateChange={onEndDateChange}
          />
        )}

        <CheckboxField
          label="Force re-download (ignore existing cache file)"
          tooltip={FORM_TOOLTIPS.forceRedownload}
          checked={force}
          onChange={onForceChange}
        />

        {downloadError ? (
          <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
            {downloadError instanceof Error
              ? downloadError.message
              : "Download failed"}
          </p>
        ) : null}

        {lastResult ? (
          <p className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-3 text-sm text-foreground">
            {lastResult}
          </p>
        ) : null}

        <button
          type="button"
          onClick={onDownload}
          disabled={isPending}
          className="btn-primary w-full"
        >
          {isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Database className="h-4 w-4" />
          )}
          Download OHLCV to CSV
        </button>
      </div>
    </Card>
  );
}
