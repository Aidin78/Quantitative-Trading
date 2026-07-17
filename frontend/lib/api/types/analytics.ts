export type AnalyticsOverview = {
  period: string;
  total_decisions: number;
  approval_rate: number;
  rejection_trends: Array<{ date: string; approved: number; rejected: number }>;
  rejection_breakdown: Record<string, number>;
  provider_contribution: Array<{ provider_id: string; count: number }>;
  by_symbol: Array<{
    symbol: string;
    total: number;
    approved: number;
    approval_rate: number;
  }>;
  outcome_summary: {
    total_trades: number;
    win_rate: number;
    total_pnl: number;
  };
};

export type AnalyticsHeatmap = {
  period: string;
  data: Array<{ hour: number; day: string; win_rate: number; trades: number }>;
};
