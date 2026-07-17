"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, Suspense } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ValidationCompareCard } from "@/components/validation/ValidationCompareCard";
import { ValidationFormCard } from "@/components/validation/ValidationFormCard";
import { ValidationHistoryCard } from "@/components/validation/ValidationHistoryCard";
import { ValidationResultsCard } from "@/components/validation/ValidationResultsCard";
import { ValidationStatusCard } from "@/components/validation/ValidationStatusCard";
import { ValidationWalkForwardCard } from "@/components/validation/ValidationWalkForwardCard";
import { useActiveValidationJob } from "@/contexts/ValidationJobContext";
import { api } from "@/lib/api";
import { dateRangeForPreset } from "@/lib/dateRange";

export default function ValidationPage() {
  return (
    <Suspense
      fallback={
        <div className="page-container flex items-center justify-center gap-2 py-24 text-muted">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
          Loading validation…
        </div>
      }
    >
      <ValidationPageContent />
    </Suspense>
  );
}

function ValidationPageContent() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    jobId,
    setActiveJobId,
    clearActiveJob,
    job,
    isActive: isJobActive,
  } = useActiveValidationJob();
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [startDate, setStartDate] = useState(
    () => dateRangeForPreset("30d").start,
  );
  const [endDate, setEndDate] = useState(() => dateRangeForPreset("30d").end);
  const [initialCapital, setInitialCapital] = useState(10000);
  const [wfWindows, setWfWindows] = useState(3);
  const [wfTrainRatio, setWfTrainRatio] = useState(0.7);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [compareRunA, setCompareRunA] = useState<string>("");
  const [compareRunB, setCompareRunB] = useState<string>("");
  const [selectedRuns, setSelectedRuns] = useState<Set<string>>(new Set());
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    const job = searchParams.get("job");
    if (job) setActiveJobId(job);
    const sym = searchParams.get("symbol");
    if (sym) setSymbol(sym);
    const start = searchParams.get("start");
    if (start) setStartDate(start);
    const end = searchParams.get("end");
    if (end) setEndDate(end);
  }, [searchParams, setActiveJobId]);

  const persistJobId = (id: string) => {
    setActiveJobId(id);
    router.replace(`/validation?job=${encodeURIComponent(id)}`, {
      scroll: false,
    });
  };

  const { data: runHistory } = useQuery({
    queryKey: ["validation-runs", symbol],
    queryFn: () => api.validationRuns({ limit: 20, symbol }),
  });

  const { data: compareData } = useQuery({
    queryKey: ["validation-compare", compareRunA, compareRunB],
    queryFn: () => api.validationCompare(compareRunA, compareRunB),
    enabled: !!compareRunA && !!compareRunB && compareRunA !== compareRunB,
  });

  const run = useMutation({
    mutationFn: () =>
      api.runValidation({
        symbol,
        start_date: startDate,
        end_date: endDate || undefined,
        source: "exchange",
        initial_capital: initialCapital,
        timeframe: "1h",
      }),
    onSuccess: (res) => persistJobId(res.id),
  });

  const cancelJob = useMutation({
    mutationFn: () => api.cancelValidation(jobId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["validation", jobId] });
    },
  });

  const walkForward = useMutation({
    mutationFn: () =>
      api.walkForward({
        symbol,
        start_date: startDate,
        end_date: endDate || undefined,
        source: "exchange",
        initial_capital: initialCapital,
        timeframe: "1h",
        windows: wfWindows,
        train_ratio: wfTrainRatio,
      }),
  });

  const { data: tradesData } = useQuery({
    queryKey: ["validation-trades", jobId],
    queryFn: () => api.validationTrades(jobId!),
    enabled: !!jobId && job?.status === "completed",
  });

  const statusVariant =
    job?.status === "completed"
      ? "success"
      : job?.status === "failed" || job?.status === "cancelled"
        ? "danger"
        : "accent";

  const progressPct =
    job?.progress && job.progress.total > 0
      ? Math.round((job.progress.current / job.progress.total) * 100)
      : 0;

  const historyItems = runHistory?.items ?? [];
  const allHistorySelected =
    historyItems.length > 0 && selectedRuns.size === historyItems.length;
  const someHistorySelected = selectedRuns.size > 0;
  const selectedRunIds = useMemo(
    () => Array.from(selectedRuns),
    [selectedRuns],
  );

  useEffect(() => {
    if (job?.status === "completed") {
      queryClient.invalidateQueries({ queryKey: ["validation-runs"] });
    }
  }, [job?.status, queryClient]);

  const invalidateHistory = () => {
    queryClient.invalidateQueries({ queryKey: ["validation-runs"] });
    setSelectedRuns(new Set());
  };

  const deleteOneRun = useMutation({
    mutationFn: (runId: string) => api.deleteValidationRun(runId),
    onSuccess: (_data, runId) => {
      setHistoryError(null);
      if (jobId === runId) clearActiveJob();
      if (compareRunA === runId) setCompareRunA("");
      if (compareRunB === runId) setCompareRunB("");
      invalidateHistory();
    },
    onError: (err) => {
      setHistoryError(err instanceof Error ? err.message : "Delete failed");
    },
  });

  const deleteManyRuns = useMutation({
    mutationFn: (runIds: string[]) => api.deleteValidationRuns(runIds),
    onSuccess: (result) => {
      setHistoryError(null);
      if (jobId && result.deleted.includes(jobId)) clearActiveJob();
      if (compareRunA && result.deleted.includes(compareRunA)) {
        setCompareRunA("");
      }
      if (compareRunB && result.deleted.includes(compareRunB)) {
        setCompareRunB("");
      }
      invalidateHistory();
    },
    onError: (err) => {
      setHistoryError(
        err instanceof Error ? err.message : "Bulk delete failed",
      );
    },
  });

  const isDeletingHistory = deleteOneRun.isPending || deleteManyRuns.isPending;

  function toggleRunSelection(runId: string) {
    setSelectedRuns((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) next.delete(runId);
      else next.add(runId);
      return next;
    });
  }

  function toggleAllHistory() {
    if (allHistorySelected) {
      setSelectedRuns(new Set());
      return;
    }
    setSelectedRuns(new Set(historyItems.map((row) => row.run_id)));
  }

  function confirmDeleteRun(runId: string) {
    if (
      !window.confirm(
        "Delete this validation run from history? Simulated trades for this run will also be removed.",
      )
    ) {
      return;
    }
    deleteOneRun.mutate(runId);
  }

  function confirmDeleteSelectedRuns() {
    if (!selectedRunIds.length) return;
    if (
      !window.confirm(
        `Delete ${selectedRunIds.length} selected validation run(s)? This cannot be undone.`,
      )
    ) {
      return;
    }
    deleteManyRuns.mutate(selectedRunIds);
  }

  async function handleExport() {
    if (!jobId) return;
    setExporting(true);
    setExportError(null);
    try {
      await api.exportValidation(jobId);
    } catch (err) {
      let msg = err instanceof Error ? err.message : "Export failed";
      try {
        const parsed = JSON.parse(msg);
        if (parsed?.detail) msg = parsed.detail;
      } catch {
        // message was not JSON; keep as-is
      }
      setExportError(msg);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="page-container">
      <PageHeader
        title="Validation Harness"
        description="Run historical backtests to measure engine quality and outcome metrics."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <ValidationFormCard
          symbol={symbol}
          onSymbolChange={setSymbol}
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
          initialCapital={initialCapital}
          onInitialCapitalChange={setInitialCapital}
          runError={run.error instanceof Error ? run.error : null}
          walkForwardError={
            walkForward.error instanceof Error ? walkForward.error : null
          }
          isRunPending={run.isPending}
          isJobActive={isJobActive}
          onRun={() => run.mutate()}
        />

        <ValidationStatusCard
          jobId={jobId}
          job={job}
          isJobActive={isJobActive}
          progressPct={progressPct}
          statusVariant={statusVariant}
          isCancelPending={cancelJob.isPending}
          onCancel={() => cancelJob.mutate()}
          exporting={exporting}
          exportError={exportError}
          onExport={handleExport}
        />
      </div>

      {job?.engine_metrics && (
        <ValidationResultsCard
          engine={job.engine_metrics}
          outcome={job.outcome_metrics}
          trades={tradesData?.trades}
        />
      )}

      <ValidationHistoryCard
        historyItems={historyItems}
        selectedRuns={selectedRuns}
        allHistorySelected={allHistorySelected}
        someHistorySelected={someHistorySelected}
        historyError={historyError}
        isDeletingHistory={isDeletingHistory}
        deletingRunId={
          deleteOneRun.isPending ? deleteOneRun.variables : undefined
        }
        isBulkDeletePending={deleteManyRuns.isPending}
        onToggleRunSelection={toggleRunSelection}
        onToggleAllHistory={toggleAllHistory}
        onConfirmDeleteRun={confirmDeleteRun}
        onConfirmDeleteSelectedRuns={confirmDeleteSelectedRuns}
        onViewRun={persistJobId}
      />

      <ValidationCompareCard
        historyItems={historyItems}
        compareRunA={compareRunA}
        compareRunB={compareRunB}
        onCompareRunAChange={setCompareRunA}
        onCompareRunBChange={setCompareRunB}
        compareData={compareData}
      />

      <ValidationWalkForwardCard
        wfWindows={wfWindows}
        onWfWindowsChange={setWfWindows}
        wfTrainRatio={wfTrainRatio}
        onWfTrainRatioChange={setWfTrainRatio}
        isPending={walkForward.isPending}
        onRun={() => walkForward.mutate()}
        result={walkForward.data}
      />
    </div>
  );
}
