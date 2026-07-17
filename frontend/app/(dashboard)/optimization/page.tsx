"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { OptimizationFormCard } from "@/components/optimization/OptimizationFormCard";
import { OptimizationModeCard } from "@/components/optimization/OptimizationModeCard";
import { OptimizationTrialsTable } from "@/components/optimization/OptimizationTrialsTable";
import { SweepResultsPanel } from "@/components/optimization/SweepResultsPanel";
import { SweepStatusCard } from "@/components/optimization/SweepStatusCard";
import { Card } from "@/components/ui/Card";
import { useActiveOptimizationSweep } from "@/contexts/OptimizationSweepContext";
import { useActiveValidationJob } from "@/contexts/ValidationJobContext";
import { api } from "@/lib/api";
import { dateRangeForPreset } from "@/lib/dateRange";
import { spaceForMode, type SweepMode } from "@/lib/optimizationSpaces";

const DEFAULT_RANGE = dateRangeForPreset("180d");

export default function OptimizationPage() {
  return (
    <Suspense
      fallback={
        <div className="page-container flex items-center justify-center gap-2 py-24 text-muted">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
          Loading optimization…
        </div>
      }
    >
      <OptimizationPageContent />
    </Suspense>
  );
}

function OptimizationPageContent() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    sweepId,
    setActiveSweepId,
    sweep,
    isActive: isSweepActive,
  } = useActiveOptimizationSweep();
  const { setActiveJobId } = useActiveValidationJob();
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [startDate, setStartDate] = useState(DEFAULT_RANGE.start);
  const [endDate, setEndDate] = useState(DEFAULT_RANGE.end);
  const [initialCapital, setInitialCapital] = useState(10000);
  const [trainRatio, setTrainRatio] = useState(0.7);
  const [maxTrials, setMaxTrials] = useState(60);
  const [topK, setTopK] = useState(5);
  const [minTrades, setMinTrades] = useState(50);
  const [walkForwardWindows, setWalkForwardWindows] = useState(1);
  const [walkForwardMode, setWalkForwardMode] = useState<"fixed" | "anchored">(
    "anchored",
  );
  const [searchMethod, setSearchMethod] = useState<"grid" | "optuna">("optuna");
  const [holdoutRatio, setHoldoutRatio] = useState(0.2);
  const [sweepMode, setSweepMode] = useState<SweepMode>("baseline");

  useEffect(() => {
    const fromUrl = searchParams.get("sweep");
    if (fromUrl) {
      setActiveSweepId(fromUrl);
    }
  }, [searchParams, setActiveSweepId]);

  const persistSweepId = (id: string) => {
    setActiveSweepId(id);
    router.replace(`/optimization?sweep=${encodeURIComponent(id)}`, {
      scroll: false,
    });
  };

  const run = useMutation({
    mutationFn: () =>
      api.runOptimization({
        symbol,
        timeframe: "1h",
        start_date: startDate,
        end_date: endDate,
        source: "exchange",
        initial_capital: initialCapital,
        train_ratio: trainRatio,
        max_trials: maxTrials,
        top_k: topK,
        min_trades: minTrades,
        holdout_ratio: holdoutRatio,
        walk_forward_windows: walkForwardWindows,
        walk_forward_mode: walkForwardMode,
        search_method: searchMethod,
        local_refine: sweepMode === "baseline",
        space: spaceForMode(sweepMode),
      }),
    onSuccess: (res) => persistSweepId(res.id),
  });

  const cancelSweep = useMutation({
    mutationFn: () => api.cancelOptimization(sweepId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["optimization", sweepId] });
    },
  });

  const apply = useMutation({
    mutationFn: (useFallback: boolean) =>
      api.applyOptimization(sweepId!, { use_fallback: useFallback }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["optimization", sweepId] });
    },
  });

  const statusVariant =
    sweep?.status === "completed"
      ? "success"
      : sweep?.status === "failed" || sweep?.status === "cancelled"
        ? "danger"
        : "accent";

  const progressPct =
    sweep?.progress && sweep.progress.total > 0
      ? Math.round((sweep.progress.current / sweep.progress.total) * 100)
      : 0;

  const topTrialIds = new Set(
    (sweep?.trials ?? [])
      .filter((t) => t.test_score != null)
      .sort(
        (a, b) =>
          (b.composite_score ?? b.test_score ?? 0) -
          (a.composite_score ?? a.test_score ?? 0),
      )
      .slice(0, topK)
      .map((t) => t.trial_id),
  );

  const bestBelowMinTrades =
    sweep?.best_valid === false ||
    (sweep?.best?.test_total_trades != null &&
      sweep.best.test_total_trades < minTrades);

  const displayTrial =
    sweep?.best_valid && sweep.best
      ? sweep.best
      : (sweep?.fallback_trial ?? sweep?.best ?? null);

  const validateHoldout = useMutation({
    mutationFn: async () => {
      if (!sweep?.holdout_start || !sweep.holdout_end || !displayTrial) {
        throw new Error("Holdout period or trial not available");
      }
      return api.runValidation({
        symbol: sweep.symbol ?? symbol,
        timeframe: sweep.timeframe ?? "1h",
        start_date: sweep.holdout_start.slice(0, 10),
        end_date: sweep.holdout_end.slice(0, 10),
        source: "exchange",
        initial_capital: initialCapital,
        revision_id: displayTrial.revision_id ?? undefined,
      });
    },
    onSuccess: (res) => {
      setActiveJobId(res.id);
      router.push(`/validation?job=${encodeURIComponent(res.id)}`);
    },
  });

  return (
    <div className="page-container">
      <PageHeader
        title="Auto Optimizer"
        description="Walk-forward grid search with composite scoring, holdout reserve, and local refinement."
      />

      <OptimizationModeCard
        sweepMode={sweepMode}
        onSelectBaseline={() => {
          setSweepMode("baseline");
          setMaxTrials(60);
          setMinTrades(50);
        }}
        onSelectDiscovery={() => {
          setSweepMode("discovery");
          setMaxTrials(40);
          setMinTrades(30);
          setSearchMethod("optuna");
        }}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <OptimizationFormCard
          symbol={symbol}
          onSymbolChange={setSymbol}
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
          trainRatio={trainRatio}
          onTrainRatioChange={setTrainRatio}
          initialCapital={initialCapital}
          onInitialCapitalChange={setInitialCapital}
          maxTrials={maxTrials}
          onMaxTrialsChange={setMaxTrials}
          topK={topK}
          onTopKChange={setTopK}
          minTrades={minTrades}
          onMinTradesChange={setMinTrades}
          walkForwardWindows={walkForwardWindows}
          onWalkForwardWindowsChange={setWalkForwardWindows}
          holdoutRatio={holdoutRatio}
          onHoldoutRatioChange={setHoldoutRatio}
          searchMethod={searchMethod}
          onSearchMethodChange={setSearchMethod}
          walkForwardMode={walkForwardMode}
          onWalkForwardModeChange={setWalkForwardMode}
          runError={run.error instanceof Error ? run.error : null}
          isRunPending={run.isPending}
          isSweepActive={isSweepActive}
          onRun={() => run.mutate()}
        />

        <SweepStatusCard
          sweepId={sweepId}
          sweep={sweep}
          isSweepActive={isSweepActive}
          progressPct={progressPct}
          statusVariant={statusVariant}
          isCancelPending={cancelSweep.isPending}
          onCancel={() => cancelSweep.mutate()}
        />
      </div>

      {sweep?.status === "completed" && displayTrial ? (
        <SweepResultsPanel
          sweep={sweep}
          displayTrial={displayTrial}
          minTrades={minTrades}
          bestBelowMinTrades={bestBelowMinTrades}
          isValidatePending={validateHoldout.isPending}
          validateError={
            validateHoldout.error instanceof Error
              ? validateHoldout.error
              : null
          }
          onValidateHoldout={() => validateHoldout.mutate()}
          isApplyPending={apply.isPending}
          applyData={apply.data}
          applyError={apply.error instanceof Error ? apply.error : null}
          onApply={() => apply.mutate(!sweep.best_valid)}
        />
      ) : null}

      {sweep?.trials?.length ? (
        <Card
          title="Trials"
          subtitle="Train scores for all candidates — click a row for test details"
        >
          <OptimizationTrialsTable
            trials={sweep.trials}
            topTrialIds={topTrialIds}
            topK={topK}
          />
        </Card>
      ) : null}
    </div>
  );
}
