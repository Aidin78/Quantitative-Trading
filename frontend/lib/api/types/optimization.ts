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
  max_parallel_trials?: number;
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
