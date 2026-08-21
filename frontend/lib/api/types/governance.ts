export type HypothesisStatus = "open" | "tested" | "confirmed" | "rejected";

export type Hypothesis = {
  hypothesis_id: string;
  observation: string;
  statement: string;
  expected_effect: string;
  proposed_change: string;
  status: HypothesisStatus;
  created_by: string;
  source_experiment_run_id?: string | null;
  tested_by_experiment_id?: string | null;
  created_at?: string;
};

export type HypothesisCreateRequest = {
  observation: string;
  statement: string;
  expected_effect: string;
  proposed_change: string;
  source_experiment_run_id?: string;
  created_by?: string;
};

export type HypothesesResponse = {
  items: Hypothesis[];
  total: number;
};

export type SimilarHypothesesRequest = {
  proposed_change: string;
  min_overlap?: number;
};

export type HypothesisGenerationJob = {
  job_id: string;
  run_id: string;
  status: "pending" | "running" | "completed" | "failed";
  hypothesis_id?: string | null;
  error?: string | null;
};

export type CandidateState =
  "candidate" | "challenger" | "champion" | "rejected" | "archived";

export type CandidateCheck = {
  name: string;
  passed: boolean;
  detail?: string | null;
};

export type Candidate = {
  candidate_id: string;
  experiment_id: string;
  hypothesis_id?: string | null;
  parent_candidate_id?: string | null;
  state: CandidateState;
  created_at?: string;
};

export type CandidateEvaluation = {
  evaluation_id: string;
  candidate_id: string;
  checks: CandidateCheck[];
  decision: "accepted" | "rejected";
  decision_reason: string;
  created_at?: string;
};

export type CandidatesResponse = {
  items: Candidate[];
  total: number;
};

export type CandidateCreateRequest = {
  experiment_id: string;
  hypothesis_id?: string;
  parent_candidate_id?: string;
};

export type ExperimentCompareResponse = {
  experiment_a_id: string;
  experiment_b_id: string;
  metrics_delta: Record<string, { a: number; b: number; delta: number }>;
  decision_diff_count: number;
  significant_cycles: unknown[];
  a_run_count: number;
  b_run_count: number;
};
