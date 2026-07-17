"use client";

import { Card } from "@/components/ui/Card";
import type { SweepMode } from "@/lib/optimizationSpaces";

type Props = {
  sweepMode: SweepMode;
  onSelectBaseline: () => void;
  onSelectDiscovery: () => void;
};

export function OptimizationModeCard({
  sweepMode,
  onSelectBaseline,
  onSelectDiscovery,
}: Props) {
  return (
    <>
      <Card
        title="Optimization mode"
        subtitle="Choose what the sweep searches"
        className="mb-6"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <button
            type="button"
            onClick={onSelectBaseline}
            className={`rounded-lg border p-4 text-left transition-colors ${
              sweepMode === "baseline"
                ? "border-accent bg-[var(--accent-dim)]"
                : "border-[var(--border)] hover:border-accent/40"
            }`}
          >
            <p className="font-medium text-foreground">Baseline tuning</p>
            <p className="mt-1 text-sm text-muted">
              EMA + RSI + MACD always on. Tune thresholds, periods, and risk
              params.
            </p>
          </button>
          <button
            type="button"
            onClick={onSelectDiscovery}
            className={`rounded-lg border p-4 text-left transition-colors ${
              sweepMode === "discovery"
                ? "border-accent bg-[var(--accent-dim)]"
                : "border-[var(--border)] hover:border-accent/40"
            }`}
          >
            <p className="font-medium text-foreground">Provider discovery</p>
            <p className="mt-1 text-sm text-muted">
              Any of 8 providers on/off + min agreeing providers. Best for
              finding the winning combo.
            </p>
          </button>
        </div>
      </Card>

      <Card
        title={
          sweepMode === "baseline" ? "Baseline workflow" : "Discovery workflow"
        }
        subtitle={
          sweepMode === "baseline"
            ? "Recommended path for EMA + RSI + MACD"
            : "Find the best provider combination"
        }
        className="mb-6"
      >
        {sweepMode === "baseline" ? (
          <ol className="list-decimal space-y-2 pl-5 text-sm text-muted">
            <li>
              Market Data — ingest{" "}
              <strong className="text-foreground">6–12 months</strong> of OHLCV
              for your symbol.
            </li>
            <li>
              Providers — click{" "}
              <strong className="text-foreground">Apply baseline</strong> to
              enable and reset EMA, RSI, and MACD.
            </li>
            <li>
              Run Optimization with the defaults below (180d, Optuna, 60
              trials).
            </li>
            <li>
              Holdout gate — click{" "}
              <strong className="text-foreground">Apply</strong> only if holdout
              passed; otherwise tune or disable one provider.
            </li>
          </ol>
        ) : (
          <ol className="list-decimal space-y-2 pl-5 text-sm text-muted">
            <li>
              Market Data — at least{" "}
              <strong className="text-foreground">180d</strong> OHLCV for your
              symbol.
            </li>
            <li>
              Select{" "}
              <strong className="text-foreground">Provider discovery</strong>{" "}
              above and run 40 Optuna trials (defaults adjust automatically).
              Each trial takes ~2–4 min on 180d data; bar-level progress appears
              while training.
            </li>
            <li>
              Review trials — active providers show as chips (EMA, RSI, ADX, …).
              Pick highest composite score on test data.
            </li>
            <li>
              Apply best config, then validate on holdout before going live.
            </li>
          </ol>
        )}
      </Card>
    </>
  );
}
