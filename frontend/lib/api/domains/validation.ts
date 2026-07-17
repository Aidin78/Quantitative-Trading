import { apiFetch, downloadExport } from "../client";
import type {
  ValidationCompareResponse,
  ValidationJob,
  ValidationRequest,
  ValidationRunsBulkDeleteResult,
  ValidationRunsResponse,
  ValidationTradesResponse,
  WalkForwardRequest,
  WalkForwardResult,
} from "../types";

export const validationApi = {
  runValidation: (body: ValidationRequest) =>
    apiFetch<{ id: string; status: string }>("/api/v1/validation/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelValidation: (id: string) =>
    apiFetch<{ id: string; status: string; message?: string }>(
      `/api/v1/validation/${id}/cancel`,
      { method: "POST" },
    ),
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
  walkForward: (body: WalkForwardRequest) =>
    apiFetch<WalkForwardResult>("/api/v1/validation/walk-forward", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  exportValidation: (id: string) =>
    downloadExport(
      `/api/v1/validation/${id}/export?format=csv`,
      `validation_${id}.csv`,
    ),
};
