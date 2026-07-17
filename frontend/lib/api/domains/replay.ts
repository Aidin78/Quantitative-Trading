import { apiFetch } from "../client";
import type {
  ConfigRevision,
  Experiment,
  ExperimentBulkDeleteResult,
  ExperimentCreateRequest,
  ReplayResult,
} from "../types";

export const replayApi = {
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
};
