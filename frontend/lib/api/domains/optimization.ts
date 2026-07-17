import { apiFetch } from "../client";
import type {
  OptimizationApplyResponse,
  OptimizationRequest,
  OptimizationSweep,
} from "../types";

export const optimizationApi = {
  runOptimization: (body: OptimizationRequest) =>
    apiFetch<{ id: string; status: string }>("/api/v1/optimization/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelOptimization: (id: string) =>
    apiFetch<{ id: string; status: string; message?: string }>(
      `/api/v1/optimization/${id}/cancel`,
      { method: "POST" },
    ),
  optimization: (id: string) =>
    apiFetch<OptimizationSweep>(`/api/v1/optimization/${id}`),
  optimizationEventsPath: (id: string) => `/api/v1/optimization/${id}/events`,
  applyOptimization: (id: string, body?: { use_fallback?: boolean }) =>
    apiFetch<OptimizationApplyResponse>(`/api/v1/optimization/${id}/apply`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
};
