import { apiFetch } from "../client";
import type {
  DecisionDetail,
  DecisionFilters,
  DecisionSummary,
  EngineConfig,
  EngineStats,
  ProviderConfig,
  SignalSummary,
} from "../types";

export const engineApi = {
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
  signals: (params?: { page?: number; limit?: number; symbol?: string }) => {
    const qs = new URLSearchParams();
    if (params?.page != null) qs.set("page", String(params.page));
    if (params?.limit != null) qs.set("limit", String(params.limit));
    if (params?.symbol) qs.set("symbol", params.symbol);
    const q = qs.toString();
    return apiFetch<{
      items: SignalSummary[];
      total: number;
      page: number;
      limit: number;
    }>(`/api/v1/signals${q ? `?${q}` : ""}`);
  },
  signal: (id: string) => apiFetch<DecisionDetail>(`/api/v1/signals/${id}`),
  providers: () => apiFetch<{ items: ProviderConfig[] }>("/api/v1/providers"),
  provider: (id: string) => apiFetch<ProviderConfig>(`/api/v1/providers/${id}`),
  patchProvider: (id: string, body: Partial<ProviderConfig>) =>
    apiFetch<ProviderConfig>(`/api/v1/providers/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  resetProvider: (id: string) =>
    apiFetch<ProviderConfig>(`/api/v1/providers/${id}/reset`, {
      method: "POST",
    }),
  resetAllProviders: () =>
    apiFetch<{ items: ProviderConfig[] }>("/api/v1/providers/reset-all", {
      method: "POST",
    }),
  applyProviderBaseline: () =>
    apiFetch<{ items: ProviderConfig[] }>("/api/v1/providers/baseline", {
      method: "POST",
    }),
};
