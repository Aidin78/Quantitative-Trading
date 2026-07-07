"use client";

import { StatCard } from "@/components/ui/Card";

function fmtNum(value: unknown, digits = 2): string {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "—";
    return value.toFixed(digits);
  }
  return value != null ? String(value) : "—";
}

function fmtPct(value: unknown): string {
  if (typeof value === "number") return `${(value * 100).toFixed(1)}%`;
  return "—";
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 px-3 py-2 text-sm">
      <span className="text-muted">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

export function ValidationMetricsPanel({
  engine,
  outcome,
}: {
  engine?: Record<string, unknown>;
  outcome?: Record<string, unknown>;
}) {
  if (!engine && !outcome) return null;

  const rejection = engine?.rejection_breakdown as
    | { by_reason?: Record<string, number>; by_stage?: Record<string, number> }
    | undefined;
  const providerContrib = engine?.provider_contribution as
    Record<string, number> | undefined;

  return (
    <div className="space-y-6">
      {engine ? (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            Engine quality
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Total cycles"
              value={fmtNum(engine.total_cycles, 0)}
            />
            <StatCard
              label="Approval rate"
              value={fmtPct(engine.approval_rate)}
              suffix=""
            />
            <StatCard label="Approved" value={fmtNum(engine.approved, 0)} />
            <StatCard label="Rejected" value={fmtNum(engine.rejected, 0)} />
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {rejection?.by_reason &&
            Object.keys(rejection.by_reason).length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted">
                  Rejections by reason
                </p>
                {Object.entries(rejection.by_reason)
                  .sort(([, a], [, b]) => b - a)
                  .map(([k, v]) => (
                    <MetricRow key={k} label={k} value={String(v)} />
                  ))}
              </div>
            ) : null}
            {providerContrib && Object.keys(providerContrib).length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted">
                  Provider contribution
                </p>
                {Object.entries(providerContrib)
                  .sort(([, a], [, b]) => b - a)
                  .map(([k, v]) => (
                    <MetricRow
                      key={k}
                      label={k.replace(/_/g, " ")}
                      value={String(v)}
                    />
                  ))}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {outcome ? (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            Outcome (PnL)
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Total trades"
              value={fmtNum(outcome.total_trades, 0)}
            />
            <StatCard
              label="Win rate"
              value={fmtPct(outcome.win_rate)}
              suffix=""
            />
            <StatCard
              label="Total PnL"
              value={fmtNum(outcome.total_pnl)}
              trend={
                typeof outcome.total_pnl === "number"
                  ? outcome.total_pnl >= 0
                    ? "up"
                    : "down"
                  : "neutral"
              }
            />
            <StatCard
              label="Max drawdown"
              value={fmtNum(outcome.max_drawdown)}
              trend="down"
            />
            <StatCard
              label="Profit factor"
              value={fmtNum(outcome.profit_factor)}
            />
            <StatCard
              label="Sharpe ratio"
              value={fmtNum(outcome.sharpe_ratio)}
            />
            <StatCard
              label="Gross profit"
              value={fmtNum(outcome.gross_profit)}
            />
            <StatCard label="Gross loss" value={fmtNum(outcome.gross_loss)} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
