const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function setToken(token: string) {
  localStorage.setItem("access_token", token);
}

export function clearToken() {
  localStorage.removeItem("access_token");
}

export async function downloadExport(
  path: string,
  filename: string,
): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => apiFetch<HealthStatus>("/health"),
  login: (username: string, password: string) =>
    apiFetch<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  decisions: (params?: string | DecisionFilters) => {
    const qs =
      typeof params === "string"
        ? params
        : params
          ? new URLSearchParams(
              Object.entries({
                ...params,
                limit: String(params.limit ?? 50),
              }).filter(([, v]) => v != null && v !== "") as [string, string][],
            ).toString()
          : "limit=50";
    return apiFetch<{ items: DecisionSummary[]; total: number }>(
      `/api/v1/decisions?${qs}`,
    );
  },
  decision: (id: string) => apiFetch<DecisionDetail>(`/api/v1/decisions/${id}`),
  stats: () => apiFetch<EngineStats>("/api/v1/engine/stats"),
  engineConfig: () =>
    apiFetch<{ engine: EngineConfig }>("/api/v1/engine/config"),
  patchEngineConfig: (body: Partial<EngineConfig>) =>
    apiFetch("/api/v1/engine/config", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  signals: () => apiFetch<{ items: SignalSummary[] }>("/api/v1/signals"),
  signal: (id: string) => apiFetch<DecisionDetail>(`/api/v1/signals/${id}`),
  providers: () => apiFetch<{ items: ProviderConfig[] }>("/api/v1/providers"),
  patchProvider: (id: string, body: Partial<ProviderConfig>) =>
    apiFetch(`/api/v1/providers/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  runValidation: (body: ValidationRequest) =>
    apiFetch<{ id: string; status: string }>("/api/v1/validation/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  validation: (id: string) =>
    apiFetch<ValidationJob>(`/api/v1/validation/${id}`),
  validationTrades: (id: string) =>
    apiFetch<ValidationTradesResponse>(`/api/v1/validation/${id}/trades`),
  validationRuns: (params?: {
    limit?: number;
    offset?: number;
    symbol?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.limit != null) qs.set("limit", String(params.limit));
    if (params?.offset != null) qs.set("offset", String(params.offset));
    if (params?.symbol) qs.set("symbol", params.symbol);
    const q = qs.toString();
    return apiFetch<ValidationRunsResponse>(
      `/api/v1/validation/runs${q ? `?${q}` : ""}`,
    );
  },
  validationCompare: (a: string, b: string) =>
    apiFetch<ValidationCompareResponse>(
      `/api/v1/validation/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`,
    ),
  deleteValidationRun: (runId: string) =>
    apiFetch<{ deleted: string }>(
      `/api/v1/validation/runs/${encodeURIComponent(runId)}`,
      { method: "DELETE" },
    ),
  deleteValidationRuns: (run_ids: string[]) =>
    apiFetch<ValidationRunsBulkDeleteResult>(
      "/api/v1/validation/runs/bulk-delete",
      {
        method: "POST",
        body: JSON.stringify({ run_ids }),
      },
    ),
  runOptimization: (body: OptimizationRequest) =>
    apiFetch<{ id: string; status: string }>("/api/v1/optimization/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  optimization: (id: string) =>
    apiFetch<OptimizationSweep>(`/api/v1/optimization/${id}`),
  applyOptimization: (id: string, body?: { use_fallback?: boolean }) =>
    apiFetch<OptimizationApplyResponse>(`/api/v1/optimization/${id}/apply`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  replay: (
    correlationId: string,
    opts?: { mode?: "strict" | "re_execute"; revision_id?: string },
  ) => {
    const params = new URLSearchParams();
    if (opts?.mode) params.set("mode", opts.mode);
    if (opts?.revision_id) params.set("revision_id", opts.revision_id);
    const qs = params.toString();
    return apiFetch<ReplayResult>(
      `/api/v1/replay/cycle/${encodeURIComponent(correlationId)}/timeline${qs ? `?${qs}` : ""}`,
    );
  },
  configRevisions: () =>
    apiFetch<{ items: ConfigRevision[]; total: number }>(
      "/api/v1/config/revisions",
    ),
  configRevision: (id: string) =>
    apiFetch<ConfigRevision>(`/api/v1/config/revisions/${id}`),
  experiments: () =>
    apiFetch<{ items: Experiment[]; total: number }>("/api/v1/experiments"),
  experiment: (id: string) => apiFetch<Experiment>(`/api/v1/experiments/${id}`),
  createExperiment: (body: ExperimentCreateRequest) =>
    apiFetch<Experiment>("/api/v1/experiments", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteExperiment: (id: string) =>
    apiFetch<{ deleted: string }>(
      `/api/v1/experiments/${encodeURIComponent(id)}`,
      {
        method: "DELETE",
      },
    ),
  deleteExperiments: (experiment_ids: string[]) =>
    apiFetch<ExperimentBulkDeleteResult>("/api/v1/experiments/bulk-delete", {
      method: "POST",
      body: JSON.stringify({ experiment_ids }),
    }),
  liveStatus: () => apiFetch<LiveStatus>("/api/v1/live/status"),
  startLive: (body: LiveStartRequest) =>
    apiFetch<LiveStatus>("/api/v1/live/start", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  stopLive: () => apiFetch<LiveStatus>("/api/v1/live/stop", { method: "POST" }),
  setLiveMode: (mode: "paper" | "live") =>
    apiFetch<LiveStatus>("/api/v1/live/mode", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
  analyticsOverview: (period = "30d") =>
    apiFetch<AnalyticsOverview>(`/api/v1/analytics/overview?period=${period}`),
  analyticsHeatmap: (period = "30d") =>
    apiFetch<AnalyticsHeatmap>(`/api/v1/analytics/heatmap?period=${period}`),
  walkForward: (body: WalkForwardRequest) =>
    apiFetch<WalkForwardResult>("/api/v1/validation/walk-forward", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  exportDecisions: () =>
    downloadExport("/api/v1/decisions/export?format=csv", "decisions.csv"),
  exportValidation: (id: string) =>
    downloadExport(
      `/api/v1/validation/${id}/export?format=csv`,
      `validation_${id}.csv`,
    ),
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
};

export type ProviderConfig = {
  provider_id: string;
  enabled: boolean;
  weight: number;
  params: Record<string, unknown>;
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
