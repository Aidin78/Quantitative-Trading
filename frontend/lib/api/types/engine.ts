export type DecisionFilters = {
  result?: string;
  side?: string;
  rejection_reason?: string;
  provider?: string;
  limit?: number;
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
  decision_id?: string;
};

export type ProviderParamField = {
  key: string;
  label: string;
  type: "float" | "int" | "bool";
  description: string;
  min?: number | null;
  max?: number | null;
  step?: number | null;
};

export type ProviderConfig = {
  provider_id: string;
  name?: string;
  enabled: boolean;
  weight: number;
  params: Record<string, unknown>;
  summary?: string;
  rules?: string[];
  default_config?: {
    enabled: boolean;
    weight: number;
    params: Record<string, unknown>;
  };
  param_fields?: ProviderParamField[];
  required_features?: string[];
};
