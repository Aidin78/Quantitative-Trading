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
