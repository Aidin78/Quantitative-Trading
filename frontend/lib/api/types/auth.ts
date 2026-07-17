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
