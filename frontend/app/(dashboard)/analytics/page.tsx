"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, Loader2, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState, StatCard } from "@/components/ui/Card";
import { api } from "@/lib/api";

const PERIODS = [
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
] as const;

const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

function heatColor(rate: number, trades: number): string {
  if (trades === 0) return "rgba(255,255,255,0.04)";
  const intensity = Math.min(rate, 1);
  return `rgba(16, 185, 129, ${0.15 + intensity * 0.65})`;
}

export default function AnalyticsPage() {
  const [period, setPeriod] = useState("30d");

  const { data, isLoading } = useQuery({
    queryKey: ["analytics", period],
    queryFn: () => api.analyticsOverview(period),
  });

  const { data: heatmap } = useQuery({
    queryKey: ["analytics-heatmap", period],
    queryFn: () => api.analyticsHeatmap(period),
  });

  const maxTrend = Math.max(
    ...(data?.rejection_trends.map((t) => t.approved + t.rejected) ?? [1]),
    1,
  );

  const heatmapGrid = useMemo(() => {
    const grid: Record<
      string,
      Record<number, { win_rate: number; trades: number }>
    > = {};
    for (const day of WEEKDAYS) {
      grid[day] = {};
      for (let hour = 0; hour < 24; hour++) {
        grid[day][hour] = { win_rate: 0, trades: 0 };
      }
    }
    for (const cell of heatmap?.data ?? []) {
      if (grid[cell.day]) {
        grid[cell.day][cell.hour] = {
          win_rate: cell.win_rate,
          trades: cell.trades,
        };
      }
    }
    return grid;
  }, [heatmap]);

  return (
    <div className="page-container">
      <PageHeader
        title="Analytics"
        description="Decision trends, provider contribution, and outcome summary."
        action={
          <select
            className="input-field text-sm"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          >
            {PERIODS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        }
      />

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-accent" />
        </div>
      ) : !data ? (
        <EmptyState message="No analytics data" />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Total Decisions"
              value={data.total_decisions}
              icon={<BarChart3 className="h-4 w-4" />}
            />
            <StatCard
              label="Approval Rate"
              value={`${(data.approval_rate * 100).toFixed(1)}`}
              suffix="%"
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <StatCard
              label="Simulated Trades"
              value={data.outcome_summary.total_trades}
            />
            <StatCard
              label="Win Rate"
              value={`${(data.outcome_summary.win_rate * 100).toFixed(1)}`}
              suffix="%"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Daily Trends" subtitle="Approvals vs rejections">
              {data.rejection_trends.length === 0 ? (
                <EmptyState message="No trend data in this period" />
              ) : (
                <div className="space-y-3">
                  {data.rejection_trends.map((trend) => {
                    const total = trend.approved + trend.rejected;
                    const approvedPct = (trend.approved / maxTrend) * 100;
                    const rejectedPct = (trend.rejected / maxTrend) * 100;
                    return (
                      <div key={trend.date}>
                        <div className="mb-1 flex justify-between text-xs text-muted">
                          <span>{trend.date}</span>
                          <span>{total} decisions</span>
                        </div>
                        <div className="flex h-2 overflow-hidden rounded-full bg-[var(--background-elevated)]">
                          <div
                            className="bg-success"
                            style={{ width: `${approvedPct}%` }}
                          />
                          <div
                            className="bg-danger"
                            style={{ width: `${rejectedPct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>

            <Card
              title="Provider Contribution"
              subtitle="Approved decisions by provider"
            >
              {data.provider_contribution.length === 0 ? (
                <EmptyState message="No provider data" />
              ) : (
                <div className="space-y-2">
                  {data.provider_contribution.map((p) => (
                    <div
                      key={p.provider_id}
                      className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-2"
                    >
                      <span className="font-mono text-sm">{p.provider_id}</span>
                      <Badge variant="accent">{p.count}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <Card
            title="Approval Heatmap"
            subtitle="Approval rate by UTC hour and weekday"
          >
            {!heatmap?.data.length ? (
              <EmptyState message="No heatmap data in this period" />
            ) : (
              <div className="overflow-x-auto">
                <div className="min-w-[48rem]">
                  <div className="mb-2 grid grid-cols-[5rem_repeat(24,minmax(0,1fr))] gap-1 text-[10px] text-muted">
                    <div />
                    {Array.from({ length: 24 }, (_, hour) => (
                      <div key={hour} className="text-center">
                        {hour}
                      </div>
                    ))}
                  </div>
                  {WEEKDAYS.map((day) => (
                    <div
                      key={day}
                      className="mb-1 grid grid-cols-[5rem_repeat(24,minmax(0,1fr))] gap-1"
                    >
                      <div className="flex items-center text-xs text-muted">
                        {day.slice(0, 3)}
                      </div>
                      {Array.from({ length: 24 }, (_, hour) => {
                        const cell = heatmapGrid[day][hour];
                        return (
                          <div
                            key={`${day}-${hour}`}
                            title={`${day} ${hour}:00 UTC — ${(cell.win_rate * 100).toFixed(0)}% (${cell.trades} decisions)`}
                            className="aspect-square rounded-sm border border-[var(--border)]/40"
                            style={{
                              backgroundColor: heatColor(
                                cell.win_rate,
                                cell.trades,
                              ),
                            }}
                          />
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {data.by_symbol.length > 0 ? (
            <Card title="By Symbol" subtitle="Approval rate per symbol">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-muted">
                      <th className="pb-2 pr-4">Symbol</th>
                      <th className="pb-2 pr-4">Total</th>
                      <th className="pb-2 pr-4">Approved</th>
                      <th className="pb-2">Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_symbol.map((row) => (
                      <tr
                        key={row.symbol}
                        className="border-b border-[var(--border)]/50"
                      >
                        <td className="py-2 pr-4 font-mono">{row.symbol}</td>
                        <td className="py-2 pr-4">{row.total}</td>
                        <td className="py-2 pr-4">{row.approved}</td>
                        <td className="py-2">
                          {(row.approval_rate * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ) : null}
        </>
      )}
    </div>
  );
}
