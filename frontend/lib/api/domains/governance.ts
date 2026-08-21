import { apiFetch } from "../client";
import type {
  Candidate,
  CandidateCreateRequest,
  CandidateEvaluation,
  CandidatesResponse,
  ExperimentCompareResponse,
  Hypothesis,
  HypothesesResponse,
  HypothesisCreateRequest,
  HypothesisGenerationJob,
  SimilarHypothesesRequest,
} from "../types";

export const governanceApi = {
  hypotheses: (params?: { status?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return apiFetch<HypothesesResponse>(
      `/api/v1/hypotheses${q ? `?${q}` : ""}`,
    );
  },
  hypothesis: (id: string) =>
    apiFetch<Hypothesis>(`/api/v1/hypotheses/${encodeURIComponent(id)}`),
  createHypothesis: (body: HypothesisCreateRequest) =>
    apiFetch<Hypothesis>("/api/v1/hypotheses", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  linkHypothesis: (id: string, experiment_id: string) =>
    apiFetch<Hypothesis>(`/api/v1/hypotheses/${encodeURIComponent(id)}/link`, {
      method: "POST",
      body: JSON.stringify({ experiment_id }),
    }),
  resolveHypothesis: (id: string, confirmed: boolean) =>
    apiFetch<Hypothesis>(
      `/api/v1/hypotheses/${encodeURIComponent(id)}/resolve`,
      {
        method: "POST",
        body: JSON.stringify({ confirmed }),
      },
    ),
  searchSimilarHypotheses: (body: SimilarHypothesesRequest) =>
    apiFetch<HypothesesResponse>("/api/v1/hypotheses/search", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generateHypothesis: (run_id: string) =>
    apiFetch<{ job_id: string; status: string }>(
      "/api/v1/hypotheses/generate",
      {
        method: "POST",
        body: JSON.stringify({ run_id }),
      },
    ),
  hypothesisGenerationJob: (jobId: string) =>
    apiFetch<HypothesisGenerationJob>(
      `/api/v1/hypotheses/generate/${encodeURIComponent(jobId)}`,
    ),

  candidates: (params?: { state?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.state) qs.set("state", params.state);
    if (params?.limit != null) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return apiFetch<CandidatesResponse>(
      `/api/v1/candidates${q ? `?${q}` : ""}`,
    );
  },
  candidate: (id: string) =>
    apiFetch<Candidate>(`/api/v1/candidates/${encodeURIComponent(id)}`),
  createCandidate: (body: CandidateCreateRequest) =>
    apiFetch<Candidate>("/api/v1/candidates", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  candidateEvaluations: (id: string) =>
    apiFetch<{ items: CandidateEvaluation[]; total: number }>(
      `/api/v1/candidates/${encodeURIComponent(id)}/evaluations`,
    ),
  promoteCandidate: (id: string, to_state: string) =>
    apiFetch<Candidate>(
      `/api/v1/candidates/${encodeURIComponent(id)}/promote`,
      {
        method: "POST",
        body: JSON.stringify({ to_state }),
      },
    ),

  experimentCompare: (a: string, b: string) =>
    apiFetch<ExperimentCompareResponse>(
      `/api/v1/experiments/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`,
    ),
};
