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
  experiment_id?: string;
  revision_id?: string;
};

export type ValidationJob = {
  id: string;
  status: string;
  engine_metrics?: Record<string, unknown>;
  outcome_metrics?: Record<string, unknown>;
  error?: string;
  revision_id?: string;
  experiment_id?: string;
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
