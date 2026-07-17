export type MarketDataDownloadRequest = {
  symbol?: string;
  timeframe?: string;
  start_date?: string;
  end_date?: string;
  months?: number;
  force?: boolean;
};

export type MarketDataDownloadResponse = {
  filename: string;
  path: string;
  exchange_id: string;
  symbol: string;
  timeframe: string;
  start: string;
  end: string;
  refreshed: boolean;
  rows: number;
  first_timestamp: string | null;
  last_timestamp: string | null;
  size_bytes: number;
};

export type MarketDataCacheEntry = {
  filename: string;
  path: string;
  updated_at: string;
  rows: number;
  first_timestamp: string | null;
  last_timestamp: string | null;
  size_bytes: number;
};
