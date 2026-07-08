"use client";

import { StatCard } from "@/components/ui/Card";
import type {
  DiagnosticsBucket,
  MonthlyBreakdownRow,
  ValidationDiagnostics,
  ValidationTrade,
} from "@/lib/api";

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

function fmtMoney(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  }
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

function DiagnosticsList({
  title,
  buckets,
}: {
  title: string;
  buckets: Record<string, DiagnosticsBucket>;
}) {
  const entries = Object.entries(buckets).sort(([, a], [, b]) => b.pnl - a.pnl);
  if (entries.length === 0) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted">{title}</p>
      {entries.map(([key, bucket]) => (
        <MetricRow
          key={key}
          label={`${key.replace(/_/g, " ")} (${bucket.trades})`}
          value={`${fmtMoney(bucket.pnl)} · ${fmtPct(bucket.win_rate)}`}
        />
      ))}
    </div>
  );
}

export function ValidationMetricsPanel({
  engine,
  outcome,
  trades,
}: {
  engine?: Record<string, unknown>;
  outcome?: Record<string, unknown>;
  trades?: ValidationTrade[];
}) {
  if (!engine && !outcome) return null;

  const rejection = engine?.rejection_breakdown as
    | { by_reason?: Record<string, number>; by_stage?: Record<string, number> }
    | undefined;
  const providerContrib = engine?.provider_contribution as
    Record<string, number> | undefined;
  const monthly = outcome?.monthly_breakdown as
    MonthlyBreakdownRow[] | undefined;
  const diagnostics = outcome?.diagnostics as ValidationDiagnostics | undefined;
  const score = typeof outcome?.score === "number" ? outcome.score : null;

  return (
    <div className="space-y-6">
      {score != null ? (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            Strategy score
          </p>
          <StatCard
            label="Composite score"
            value={score.toFixed(1)}
            trend={score >= 0 ? "up" : "down"}
            suffix="/ 100"
          />
        </div>
      ) : null}

      {monthly && monthly.length > 0 ? (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            Monthly breakdown
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
                  <th className="pb-2 pr-3">Month</th>
                  <th className="pb-2 pr-3">Trades</th>
                  <th className="pb-2 pr-3">Win rate</th>
                  <th className="pb-2 pr-3">PnL</th>
                  <th className="pb-2 pr-3">Return</th>
                  <th className="pb-2">Max DD</th>
                </tr>
              </thead>
              <tbody>
                {monthly.map((row) => (
                  <tr
                    key={row.month}
                    className="border-b border-[var(--border)]/50"
                  >
                    <td className="py-2 pr-3 font-mono text-xs">{row.month}</td>
                    <td className="py-2 pr-3">{row.trades}</td>
                    <td className="py-2 pr-3">{fmtPct(row.win_rate)}</td>
                    <td
                      className={`py-2 pr-3 font-mono text-xs ${row.pnl >= 0 ? "text-[var(--success)]" : "text-danger"}`}
                    >
                      {fmtNum(row.pnl)}
                    </td>
                    <td
                      className={`py-2 pr-3 font-mono text-xs ${row.return_pct >= 0 ? "text-[var(--success)]" : "text-danger"}`}
                    >
                      {row.return_pct.toFixed(2)}%
                    </td>
                    <td className="py-2 font-mono text-xs">
                      {row.max_drawdown_pct.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {diagnostics ? (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            Diagnostics
          </p>
          <div className="grid gap-4 lg:grid-cols-3">
            <DiagnosticsList
              title="By exit reason"
              buckets={diagnostics.by_exit_reason}
            />
            <DiagnosticsList
              title="By session (UTC)"
              buckets={diagnostics.by_session}
            />
            <DiagnosticsList title="By side" buckets={diagnostics.by_side} />
          </div>
        </div>
      ) : null}

      {outcome && typeof outcome.initial_capital === "number" ? (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            Capital simulation
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Initial capital"
              value={fmtMoney(outcome.initial_capital)}
            />
            <StatCard
              label="Ending equity"
              value={fmtMoney(outcome.ending_equity)}
            />
            <StatCard
              label="Return"
              value={
                typeof outcome.return_pct === "number"
                  ? `${outcome.return_pct.toFixed(2)}%`
                  : "—"
              }
              trend={
                typeof outcome.return_pct === "number"
                  ? outcome.return_pct >= 0
                    ? "up"
                    : "down"
                  : "neutral"
              }
            />
            <StatCard
              label="Max drawdown"
              value={
                typeof outcome.max_drawdown_pct === "number"
                  ? `${outcome.max_drawdown_pct.toFixed(2)}%`
                  : fmtNum(outcome.max_drawdown)
              }
              trend="down"
            />
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <MetricRow
              label="Positions opened"
              value={fmtNum(outcome.positions_opened, 0)}
            />
            <MetricRow
              label="Positions closed"
              value={fmtNum(outcome.positions_closed, 0)}
            />
            <MetricRow
              label="Orders rejected"
              value={fmtNum(outcome.orders_rejected, 0)}
            />
          </div>
        </div>
      ) : null}

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

      {trades && trades.length > 0 ? (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            Trade ledger
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
                  <th className="pb-2 pr-3">Side</th>
                  <th className="pb-2 pr-3">Entry</th>
                  <th className="pb-2 pr-3">Exit</th>
                  <th className="pb-2 pr-3">SL / TP</th>
                  <th className="pb-2 pr-3">Exit reason</th>
                  <th className="pb-2 pr-3">PnL</th>
                  <th className="pb-2">Result</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr
                    key={t.position_id}
                    className="border-b border-[var(--border)]/50"
                  >
                    <td className="py-2 pr-3 font-medium">{t.side}</td>
                    <td className="py-2 pr-3 font-mono text-xs">
                      {fmtNum(t.entry_price)}
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs">
                      {fmtNum(t.exit_price)}
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs text-muted">
                      {t.stop_loss != null ? fmtNum(t.stop_loss) : "—"} /{" "}
                      {t.take_profit != null ? fmtNum(t.take_profit) : "—"}
                    </td>
                    <td className="py-2 pr-3 text-xs">{t.exit_reason}</td>
                    <td
                      className={`py-2 pr-3 font-mono text-xs ${t.pnl >= 0 ? "text-[var(--success)]" : "text-danger"}`}
                    >
                      {fmtNum(t.pnl)}
                    </td>
                    <td className="py-2 text-xs">{t.win ? "Win" : "Loss"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
