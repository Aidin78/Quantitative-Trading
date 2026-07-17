export type DecisionFilters = {
  result?: string;
  side?: string;
  rejection_reason?: string;
  provider?: string;
  limit?: number;
};

export type HealthStatus = {
  status: string;
  phase: string;
  environment: string;
  app: string;
  default_symbol?: string;
  default_timeframe?: string;
  symbols?: string[];
  timeframes?: string[];
};

export type DecisionSummary = {
  id: string;
  symbol: string;
  timeframe: string;
  result: string;
  side?: string;
  confidence?: number;
  rejection_reason?: string;
  rejection_stage?: string;
  provider_ids: string[];
  timestamp: string;
  correlation_id: string;
  revision_id?: string | null;
  experiment_id?: string | null;
};

export type DecisionDetail = DecisionSummary & {
  final_signal?: Record<string, unknown>;
  decision_log: Record<string, unknown>;
  provider_signals: Array<Record<string, unknown>>;
  feature_snapshot?: Record<string, unknown>;
  market_context?: Record<string, unknown>;
  explainability: {
    summary: string;
    correlation_id: string;
    causal_chain_url: string;
  };
};

export type EngineStats = {
  decisions_today: number;
  approval_rate: number;
  rejection_breakdown: Record<string, number>;
  active_providers: number;
};

export type EngineConfig = {
  aggregation: Record<string, unknown>;
  filter: Record<string, unknown>;
  risk: Record<string, unknown>;
};

export type SignalSummary = {
  id: string;
  symbol: string;
  side: string;
  confidence: number;
  timestamp: string;
  decision_id?: string;
};

export type ProviderParamField = {
  key: string;
  label: string;
  type: "float" | "int" | "bool";
  description: string;
  min?: number | null;
  max?: number | null;
  step?: number | null;
};

export type ProviderConfig = {
  provider_id: string;
  name?: string;
  enabled: boolean;
  weight: number;
  params: Record<string, unknown>;
  summary?: string;
  rules?: string[];
  default_config?: {
    enabled: boolean;
    weight: number;
    params: Record<string, unknown>;
  };
  param_fields?: ProviderParamField[];
  required_features?: string[];
};

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

export type OptimizationRequest = {
  symbol?: string;
  timeframe?: string;
  start_date?: string;
  end_date?: string;
  source?: "exchange" | "csv";
  initial_capital?: number;
  train_ratio?: number;
  max_trials?: number;
  top_k?: number;
  space?: Record<string, Array<number | string>>;
  csv_path?: string;
  seed?: number;
  min_trades?: number;
  min_return_pct?: number;
  holdout_ratio?: number;
  walk_forward_windows?: number;
  walk_forward_mode?: "fixed" | "anchored";
  local_refine?: boolean;
  search_method?: "grid" | "optuna";
  min_trades_holdout?: number;
};

export type OptimizationHoldoutMetrics = {
  return_pct?: number;
  total_trades?: number;
  score?: number;
  sharpe_ratio?: number;
  sortino_ratio?: number;
  max_drawdown_pct?: number;
};

export type OptimizationTrial = {
  trial_id: string;
  params: Record<string, number | string>;
  train_score: number;
  test_score?: number | null;
  stability?: number | null;
  composite_score?: number | null;
  fold_scores?: number[];
  fold_std?: number | null;
  pareto_rank?: number | null;
  revision_id?: string | null;
  train_total_trades?: number;
  train_return_pct?: number;
  test_total_trades?: number | null;
  test_return_pct?: number | null;
};

export type OptimizationSweep = {
  id: string;
  status: string;
  config?: Record<string, unknown>;
  phase?: string;
  message?: string;
  elapsed_seconds?: number;
  progress?: { current: number; total: number };
  error?: string;
  sweep_id?: string;
  symbol?: string;
  timeframe?: string;
  train_start?: string;
  train_end?: string;
  test_start?: string;
  test_end?: string;
  holdout_start?: string | null;
  holdout_end?: string | null;
  optimization_end?: string | null;
  trials?: OptimizationTrial[];
  best?: OptimizationTrial | null;
  best_valid?: boolean;
  selection_message?: string | null;
  fallback_trial?: OptimizationTrial | null;
  holdout_score?: number | null;
  holdout_valid?: boolean;
  holdout_metrics?: OptimizationHoldoutMetrics | null;
};

export type OptimizationApplyResponse = {
  sweep_id: string;
  revision_id: string;
  applied_params: Record<string, number | string>;
  applied_from?: "best" | "fallback";
  best?: OptimizationTrial | null;
  holdout_start?: string | null;
  holdout_end?: string | null;
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

export type DecisionDiff = {
  correlation_id: string;
  original: {
    result: string;
    side?: string | null;
    rejection_reason?: string | null;
    confidence?: number | null;
  };
  reexecuted: {
    result: string;
    side?: string | null;
    rejection_reason?: string | null;
    confidence?: number | null;
  };
  changed: boolean;
  revision_id?: string | null;
};

export type ReplayResult = {
  correlation_id: string;
  mode: "strict" | "re_execute";
  timeline: TimelineEntry[];
  families_present?: string[];
  decision_diff?: DecisionDiff;
  feature_drift?: FeatureDrift;
  causal_graph?: CausalGraph;
};

export type ConfigRevision = {
  revision_id: string;
  created_at: string;
  engine_config_hash: string;
  features_config_hash: string;
  providers_config_hash: string;
  label: string;
  parent_revision_id?: string | null;
};

export type Experiment = {
  experiment_id: string;
  name: string;
  description: string;
  revision_id: string;
  status: string;
  mode: string;
  symbols: string[];
  timeframes: string[];
  hypothesis?: string | null;
};

export type ExperimentCreateRequest = {
  name: string;
  revision_id?: string;
  mode?: string;
  description?: string;
  hypothesis?: string;
};

export type ExperimentBulkDeleteResult = {
  deleted: string[];
  not_found: string[];
  blocked: string[];
  deleted_count: number;
};

export type TimelineEntry = {
  event_id?: string;
  event_type: string;
  event_time: string;
  event_family?: string;
  causation_id?: string | null;
  summary?: string;
};

export type FeatureDrift = {
  detected?: boolean;
  drifted_features?: string[];
  config_hash_stored?: string;
  config_hash_current?: string;
  reason?: string;
};

export type CausalGraph = {
  nodes: Array<{
    id: string;
    event_type: string;
    event_family: string;
    event_time: string;
  }>;
  edges: Array<{ from: string; to: string; relation: string }>;
  roots: string[];
};

export type AnalyticsOverview = {
  period: string;
  total_decisions: number;
  approval_rate: number;
  rejection_trends: Array<{ date: string; approved: number; rejected: number }>;
  rejection_breakdown: Record<string, number>;
  provider_contribution: Array<{ provider_id: string; count: number }>;
  by_symbol: Array<{
    symbol: string;
    total: number;
    approved: number;
    approval_rate: number;
  }>;
  outcome_summary: {
    total_trades: number;
    win_rate: number;
    total_pnl: number;
  };
};

export type AnalyticsHeatmap = {
  period: string;
  data: Array<{ hour: number; day: string; win_rate: number; trades: number }>;
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
