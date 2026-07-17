export type ValidationRequest = {
  symbol?: string;
  timeframe?: string;
  start_date?: string;
  end_date?: string;
  source?: "exchange" | "csv";
  initial_capital?: number;
  experiment_id?: string;
  revision_id?: string;
};

export type ValidationTrade = {
  position_id: string;
  symbol: string;
  side?: string;
  entry_price: number;
  exit_price: number;
  stop_loss?: number;
  take_profit?: number;
  quantity?: number;
  exit_reason?: string;
  pnl: number;
  return_pct: number;
  bars_held?: number;
  entry_time?: string;
  exit_time?: string;
  win: boolean;
};

export type ValidationTradesResponse = {
  run_id: string;
  trades: ValidationTrade[];
  total: number;
};

export type MonthlyBreakdownRow = {
  month: string;
  trades: number;
  win_rate: number;
  pnl: number;
  return_pct: number;
  max_drawdown_pct: number;
  start_equity: number;
  end_equity: number;
};

export type DiagnosticsBucket = {
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  pnl: number;
  gross_profit: number;
  gross_loss: number;
};

export type ValidationDiagnostics = {
  by_exit_reason: Record<string, DiagnosticsBucket>;
  by_session: Record<string, DiagnosticsBucket>;
  by_side: Record<string, DiagnosticsBucket>;
};

export type ValidationRunSummary = {
  run_id: string;
  symbol: string;
  timeframe: string;
  start?: string;
  end?: string;
  initial_capital?: number;
  revision_id?: string;
  experiment_id?: string;
  completed_at?: string | null;
  total_trades: number;
  win_rate: number;
  return_pct: number;
  score: number;
  total_pnl: number;
};

export type ValidationRunsResponse = {
  items: ValidationRunSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type ValidationRunsBulkDeleteResult = {
  deleted: string[];
  not_found: string[];
  deleted_count: number;
};

export type ValidationCompareMetric = {
  a: number;
  b: number;
  delta: number;
  winner: "a" | "b" | "tie";
};

export type ValidationCompareResponse = {
  a: ValidationRunSummary;
  b: ValidationRunSummary;
  metrics: Record<string, ValidationCompareMetric>;
  overall_winner: "a" | "b" | "tie";
  revision_diff?: {
    a?: Record<string, unknown> | null;
    b?: Record<string, unknown> | null;
    same_revision?: boolean;
    engine_hash_match?: boolean | null;
    providers_hash_match?: boolean | null;
  } | null;
};

export type ValidationJob = {
  id: string;
  status: string;
  phase?: string;
  message?: string;
  elapsed_seconds?: number;
  progress?: { current: number; total: number };
  engine_metrics?: Record<string, unknown>;
  outcome_metrics?: Record<string, unknown>;
  error?: string;
  revision_id?: string;
  experiment_id?: string;
  run_id?: string;
};

export type WalkForwardRequest = {
  symbol?: string;
  timeframe?: string;
  start_date?: string;
  end_date?: string;
  source?: "exchange" | "csv";
  initial_capital?: number;
  windows?: number;
  train_ratio?: number;
};

export type WalkForwardResult = {
  symbol: string;
  timeframe: string;
  windows: Array<{
    window: number;
    test_start: string;
    test_end: string;
    status: string;
    engine_metrics?: Record<string, unknown>;
    outcome_metrics?: Record<string, unknown>;
    error?: string;
  }>;
};
