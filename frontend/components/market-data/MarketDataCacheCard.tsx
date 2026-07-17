"use client";

import { Download, Loader2, RefreshCw } from "lucide-react";
import { formatBytes } from "@/components/market-data/formatBytes";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { api, type MarketDataCacheEntry } from "@/lib/api";

type Props = {
  items: MarketDataCacheEntry[] | undefined;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  isFetching: boolean;
  onRefetch: () => void;
};

export function MarketDataCacheCard({
  items,
  isLoading,
  isError,
  error,
  isFetching,
  onRefetch,
}: Props) {
  return (
    <Card title="Cached CSV Files" subtitle="Files already on the server">
      {isLoading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="h-6 w-6 animate-spin text-accent" />
        </div>
      ) : isError ? (
        <div className="space-y-3 py-6 text-center">
          <p className="text-sm text-danger">
            {error instanceof Error
              ? error.message
              : "Failed to load cache list"}
          </p>
          <p className="text-xs text-muted">
            Make sure the backend is running on port 8000.
          </p>
          <button
            type="button"
            className="btn-secondary mx-auto text-xs"
            onClick={onRefetch}
            disabled={isFetching}
          >
            {isFetching ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RefreshCw className="h-3 w-3" />
            )}
            Retry
          </button>
        </div>
      ) : !items?.length ? (
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
              {items.map((row) => (
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
      {items?.length ? (
        <div className="mt-4 flex items-center gap-2 text-xs text-muted">
          <RefreshCw className="h-3 w-3" />
          <span>
            {items.length} file{items.length === 1 ? "" : "s"} in cache
          </span>
          <Badge variant="accent">{items[0].filename}</Badge>
          <span>is the most recent</span>
        </div>
      ) : null}
    </Card>
  );
}
