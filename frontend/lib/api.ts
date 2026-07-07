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
  login: (username: string, password: string) =>
    apiFetch<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  decisions: (params?: string) =>
    apiFetch<{ items: DecisionSummary[]; total: number }>(
      `/api/v1/decisions${params ? `?${params}` : ""}`,
    ),
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
  replay: (correlationId: string) =>
    apiFetch<{ timeline: TimelineEntry[] }>(
      `/api/v1/replay/cycle/${correlationId}/timeline`,
    ),
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
};

export type ValidationJob = {
  id: string;
  status: string;
  engine_metrics?: Record<string, unknown>;
  outcome_metrics?: Record<string, unknown>;
  error?: string;
};

export type TimelineEntry = {
  event_type: string;
  event_time: string;
  event_family?: string;
  summary?: string;
};
