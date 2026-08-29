"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Layers, Loader2, Scale, TrendingUp } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState, StatCard } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { CarrySleeve, CoreSleeve } from "@/lib/api/types";

const money = (v: number | null | undefined) =>
  v == null
    ? "—"
    : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const pct = (v: number | null | undefined, digits = 2) =>
  v == null ? "—" : `${v.toFixed(digits)}%`;
const qty = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(6));
const when = (v: string | null | undefined) =>
  v ? new Date(v).toLocaleString() : "—";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--border)]/50 py-2 text-sm last:border-0">
      <span className="text-muted">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

function carryVariant(status: CarrySleeve["status"]) {
  if (status === "in_market") return "success" as const;
  if (status === "flat") return "warning" as const;
  return "default" as const;
}

function coreVariant(status: string) {
  if (status === "running") return "success" as const;
  if (status === "paused") return "warning" as const;
  return "default" as const;
}

export default function PortfolioPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.portfolio(),
    refetchInterval: 30_000,
  });

  const carry = data?.carry;
  const core = data?.core;
  const blend = data?.blend;

  const notStarted =
    carry?.status === "not_started" &&
    (core?.status ?? "stopped") === "stopped";

  return (
    <div className="page-container">
      <PageHeader
        title="Book"
        description="The deployable book — the delta-neutral carry sleeve and the trend-core sleeve, plus the target blend. Neither runs through the Decision Engine."
      />

      {isLoading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-muted">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
          Loading book…
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-danger/30 bg-[var(--danger-dim)] p-4">
          <p className="font-medium text-danger">Failed to load the book</p>
          <p className="mt-1 text-sm text-muted">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
          <button
            type="button"
            className="btn-secondary mt-3 text-xs"
            onClick={() => refetch()}
          >
            Retry
          </button>
        </div>
      ) : notStarted ? (
        <EmptyState
          message="Neither sleeve is running"
          hint="Start the carry runner with scripts/run_carry_live.py, or start the trend-core engine from the Decision Monitor."
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Carry equity"
              value={money(carry?.equity)}
              icon={<Scale className="h-4 w-4" />}
            />
            <StatCard
              label="Funding APR"
              value={pct(carry?.funding_apr_pct, 1)}
              trend={
                carry?.funding_apr_pct == null
                  ? undefined
                  : carry.funding_apr_pct > 0
                    ? "up"
                    : "down"
              }
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <StatCard
              label="Net delta"
              value={pct(carry?.net_delta_pct, 2)}
              icon={<Activity className="h-4 w-4" />}
            />
            <StatCard
              label="Core engine"
              value={core?.status ?? "stopped"}
              icon={<Layers className="h-4 w-4" />}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <CarryCard carry={carry} />
            <CoreCard core={core} />
          </div>

          {blend ? (
            <Card
              title="Target blend"
              subtitle="70% carry · 30% trend core, vol-targeted (docs/development/basis-carry-findings.md)"
            >
              <div className="flex h-3 overflow-hidden rounded-full bg-[var(--background-elevated)]">
                <div
                  className="bg-accent"
                  style={{ width: `${blend.target_carry_pct}%` }}
                />
                <div
                  className="bg-success"
                  style={{ width: `${blend.target_core_pct}%` }}
                />
              </div>
              <div className="mt-2 flex justify-between text-xs text-muted">
                <span>Carry {blend.target_carry_pct.toFixed(0)}%</span>
                <span>Core {blend.target_core_pct.toFixed(0)}%</span>
              </div>
              <p className="mt-4 text-xs text-muted/70">{blend.note}</p>
            </Card>
          ) : null}
        </>
      )}
    </div>
  );
}

function CarryCard({ carry }: { carry?: CarrySleeve }) {
  if (!carry || carry.status === "not_started") {
    return (
      <Card title="Carry sleeve" subtitle="Delta-neutral basis carry">
        <EmptyState
          message="Carry runner has not run"
          hint="poetry run python scripts/run_carry_live.py --once"
        />
      </Card>
    );
  }
  return (
    <Card
      title="Carry sleeve"
      subtitle={
        carry.symbol
          ? `Delta-neutral · ${carry.symbol}`
          : "Delta-neutral basis carry"
      }
    >
      <div className="mb-3 flex flex-wrap gap-2">
        <Badge variant={carryVariant(carry.status)} dot>
          {carry.status.replace("_", " ")}
        </Badge>
        {carry.is_dry_run ? <Badge variant="warning">dry run</Badge> : null}
      </div>
      <Row label="Equity" value={money(carry.equity)} />
      <Row label="Accrued funding" value={money(carry.accrued_funding)} />
      <Row label="Funding (8h)" value={pct(carry.funding_8h_pct, 4)} />
      <Row label="Funding (APR)" value={pct(carry.funding_apr_pct, 1)} />
      <Row label="Spot qty" value={qty(carry.spot_qty)} />
      <Row label="Perp qty" value={qty(carry.perp_qty)} />
      <Row label="Notional" value={money(carry.notional)} />
      <Row
        label="Net delta"
        value={`${qty(carry.net_delta_qty)} (${pct(carry.net_delta_pct, 2)})`}
      />
      <Row label="Re-strikes (flips)" value={carry.flips ?? 0} />
      <Row label="Last action" value={carry.last_action ?? "—"} />
      <Row label="Marked at" value={when(carry.marked_at)} />
    </Card>
  );
}

function CoreCard({ core }: { core?: CoreSleeve }) {
  if (!core) return null;
  return (
    <Card
      title="Trend-core sleeve"
      subtitle="Regime gate + vol targeting (core_long)"
    >
      <div className="mb-3">
        <Badge variant={coreVariant(core.status)} dot>
          {core.status}
        </Badge>
      </div>
      <Row label="Mode" value={core.mode ?? "—"} />
      <Row label="Revision" value={core.revision_id ?? "—"} />
      <Row label="Experiment" value={core.experiment_id ?? "—"} />
      <Row label="Last run" value={when(core.last_run_at)} />
      {core.last_error ? (
        <Row
          label="Last error"
          value={<span className="text-danger">{core.last_error}</span>}
        />
      ) : null}
      {core.jobs.length ? (
        <div className="mt-3 space-y-1 text-xs text-muted">
          {core.jobs.map((j) => (
            <div
              key={`${j.symbol}-${j.timeframe}`}
              className="flex justify-between"
            >
              <span className="font-mono">
                {j.symbol} · {j.timeframe}
              </span>
              <span>
                {j.next_run_at ? new Date(j.next_run_at).toLocaleString() : "—"}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      <Link href="/" className="btn-secondary mt-4 w-full text-xs">
        Open Decision Monitor
      </Link>
    </Card>
  );
}
