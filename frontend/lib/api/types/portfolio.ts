export type CarrySleeve = {
  status: "not_started" | "flat" | "in_market";
  symbol?: string | null;
  updated_at?: string | null;
  marked_at?: string | null;
  is_dry_run?: boolean;
  equity?: number | null;
  cash?: number;
  accrued_funding?: number;
  funding_8h_pct?: number | null;
  funding_apr_pct?: number | null;
  spot_qty?: number;
  perp_qty?: number;
  notional?: number;
  net_delta_qty?: number;
  net_delta_pct?: number;
  flips?: number;
  last_action?: string | null;
};

export type CoreSleeve = {
  status: string;
  mode?: string | null;
  revision_id?: string | null;
  experiment_id?: string | null;
  last_run_at?: string | null;
  last_error?: string | null;
  jobs: Array<{
    symbol: string;
    timeframe: string;
    next_run_at?: string | null;
  }>;
};

export type PortfolioBlend = {
  target_carry_pct: number;
  target_core_pct: number;
  combined_equity: number | null;
  note: string;
};

export type Portfolio = {
  carry: CarrySleeve;
  core: CoreSleeve;
  blend: PortfolioBlend;
};
