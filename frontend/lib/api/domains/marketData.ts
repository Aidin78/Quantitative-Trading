import { apiFetch, downloadExport } from "../client";
import type {
  MarketDataCacheEntry,
  MarketDataDownloadRequest,
  MarketDataDownloadResponse,
} from "../types";

export const marketDataApi = {
  marketDataCache: () =>
    apiFetch<{ items: MarketDataCacheEntry[] }>("/api/v1/market-data/cache"),
  downloadMarketData: (body: MarketDataDownloadRequest) =>
    apiFetch<MarketDataDownloadResponse>("/api/v1/market-data/download", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  exportMarketDataCache: (filename: string) =>
    downloadExport(
      `/api/v1/market-data/cache/${encodeURIComponent(filename)}/file`,
      filename,
    ),
};
