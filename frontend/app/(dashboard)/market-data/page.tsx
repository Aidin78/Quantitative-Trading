"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Download, Loader2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { DateRangeFields } from "@/components/ui/DateRangeFields";
import { api } from "@/lib/api";
import { dateRangeForPreset } from "@/lib/dateRange";

const MONTH_PRESETS = [
  { months: 1, label: "1 month" },
  { months: 3, label: "3 months" },
  { months: 6, label: "6 months" },
] as const;

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function MarketDataPage() {
  const queryClient = useQueryClient();
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [months, setMonths] = useState(3);
  const [useCustomRange, setUseCustomRange] = useState(false);
  const [startDate, setStartDate] = useState(
    () => dateRangeForPreset("90d").start,
  );
  const [endDate, setEndDate] = useState(() => dateRangeForPreset("90d").end);
  const [force, setForce] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const { data: cache, isLoading } = useQuery({
    queryKey: ["market-data-cache"],
    queryFn: () => api.marketDataCache(),
  });

  const download = useMutation({
    mutationFn: () =>
      api.downloadMarketData({
        symbol,
        timeframe,
        months: useCustomRange ? undefined : months,
        start_date: useCustomRange ? startDate : undefined,
        end_date: useCustomRange ? endDate : undefined,
        force,
      }),
    onSuccess: (res) => {
      setLastResult(
        res.refreshed
          ? `Downloaded ${res.rows.toLocaleString()} bars → ${res.filename}`
          : `Used cached file (${res.rows.toLocaleString()} bars) → ${res.filename}`,
      );
      queryClient.invalidateQueries({ queryKey: ["market-data-cache"] });
    },
  });

  return (
    <div className="page-container">
      <PageHeader
        title="Market Data"
        description="Download OHLCV from Binance once and cache it as CSV for validation and optimization."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          title="Download & Cache"
          subtitle="One request fetches the full range and saves it on the server"
        >
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  Symbol
                </label>
                <input
                  className="input-field mt-2"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  Timeframe
                </label>
                <select
                  className="input-field mt-2"
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                >
                  <option value="1h">1h</option>
                  <option value="4h">4h</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium uppercase tracking-wider text-muted">
                Range Mode
              </label>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  className={`btn-secondary px-2.5 py-1 text-xs ${!useCustomRange ? "ring-1 ring-accent" : ""}`}
                  onClick={() => setUseCustomRange(false)}
                >
                  Last N months
                </button>
                <button
                  type="button"
                  className={`btn-secondary px-2.5 py-1 text-xs ${useCustomRange ? "ring-1 ring-accent" : ""}`}
                  onClick={() => setUseCustomRange(true)}
                >
                  Custom dates
                </button>
              </div>
            </div>

            {!useCustomRange ? (
              <div>
                <label className="text-xs font-medium uppercase tracking-wider text-muted">
                  Period
                </label>
                <div className="mt-2 flex flex-wrap gap-2">
                  {MONTH_PRESETS.map((preset) => (
                    <button
                      key={preset.months}
                      type="button"
                      className={`btn-secondary px-2.5 py-1 text-xs ${months === preset.months ? "ring-1 ring-accent" : ""}`}
                      onClick={() => setMonths(preset.months)}
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
                onStartDateChange={setStartDate}
                onEndDateChange={setEndDate}
              />
            )}

            <label className="flex items-center gap-2 text-sm text-muted">
              <input
                type="checkbox"
                checked={force}
                onChange={(e) => setForce(e.target.checked)}
              />
              Force re-download (ignore existing cache file)
            </label>

            {download.error ? (
              <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-sm text-danger">
                {download.error instanceof Error
                  ? download.error.message
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
              onClick={() => download.mutate()}
              disabled={download.isPending}
              className="btn-primary w-full"
            >
              {download.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Database className="h-4 w-4" />
              )}
              Download OHLCV to CSV
            </button>
          </div>
        </Card>

        <Card
          title="How it works"
          subtitle="Cached files are reused by Validation and Optimizer"
        >
          <div className="space-y-3 text-sm text-muted">
            <p>
              Pick a symbol and range, then send one request. The backend pulls
              OHLCV from Binance (paginated) and writes a CSV under{" "}
              <code className="text-xs text-foreground">
                backend/data/cache/
              </code>
              .
            </p>
            <p>
              When you run Validation or Auto Optimizer with{" "}
              <strong className="text-foreground">Exchange</strong> as the data
              source, the same cache file is reused — no repeat download unless
              you force refresh or change the date range.
            </p>
            <p>
              For quick testing without Binance, keep using{" "}
              <strong className="text-foreground">Sample CSV</strong> on those
              pages.
            </p>
          </div>
        </Card>
      </div>

      <Card title="Cached CSV Files" subtitle="Files already on the server">
        {isLoading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-6 w-6 animate-spin text-accent" />
          </div>
        ) : !cache?.items.length ? (
          <EmptyState
            message="No cached CSV files yet"
            hint="Download 3 months of BTC/USDT above"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
                  <th className="pb-2 pr-3">File</th>
                  <th className="pb-2 pr-3">Bars</th>
                  <th className="pb-2 pr-3">Range</th>
                  <th className="pb-2 pr-3">Size</th>
                  <th className="pb-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {cache.items.map((row) => (
                  <tr
                    key={row.filename}
                    className="border-b border-[var(--border)]/50"
                  >
                    <td className="py-2 pr-3 font-mono text-xs">
                      {row.filename}
                    </td>
                    <td className="py-2 pr-3">{row.rows.toLocaleString()}</td>
                    <td className="py-2 pr-3 font-mono text-xs">
                      {row.first_timestamp?.slice(0, 10) ?? "—"} →{" "}
                      {row.last_timestamp?.slice(0, 10) ?? "—"}
                    </td>
                    <td className="py-2 pr-3 text-xs text-muted">
                      {formatBytes(row.size_bytes)}
                    </td>
                    <td className="py-2">
                      <button
                        type="button"
                        className="btn-secondary text-xs"
                        onClick={() => api.exportMarketDataCache(row.filename)}
                      >
                        <Download className="h-3 w-3" />
                        Save
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {cache?.items.length ? (
          <div className="mt-4 flex items-center gap-2 text-xs text-muted">
            <RefreshCw className="h-3 w-3" />
            <span>
              {cache.items.length} file{cache.items.length === 1 ? "" : "s"} in
              cache
            </span>
            <Badge variant="accent">{cache.items[0].filename}</Badge>
            <span>is the most recent</span>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
