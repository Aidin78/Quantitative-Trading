export type LiveJob = {
  symbol: string;
  timeframe: string;
  next_run_at?: string | null;
};

export type LiveStatus = {
  status: "stopped" | "running" | "paused";
  mode: "paper" | "live";
  exchange_connected: boolean;
  alerts_connected: boolean;
  last_run_at?: string | null;
  last_signal_at?: string | null;
  last_error?: string | null;
  revision_id?: string | null;
  experiment_id?: string | null;
  jobs: LiveJob[];
};

export type LiveStartRequest = {
  mode?: "paper" | "live";
  symbol?: string;
  timeframe?: string;
  revision_id?: string;
  experiment_id?: string;
};
