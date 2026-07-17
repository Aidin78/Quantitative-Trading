"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { buildGraphTree } from "@/components/replay/buildGraphTree";
import { ReplayCausalGraphCard } from "@/components/replay/ReplayCausalGraphCard";
import { ReplayDecisionDiffCard } from "@/components/replay/ReplayDecisionDiffCard";
import { ReplayDriftBanner } from "@/components/replay/ReplayDriftBanner";
import { ReplayErrorBanner } from "@/components/replay/ReplayErrorBanner";
import { ReplaySearchCard } from "@/components/replay/ReplaySearchCard";
import { ReplayTimelineCard } from "@/components/replay/ReplayTimelineCard";
import { EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

function ReplayContent() {
  const params = useSearchParams();
  const urlCorrelationId = params.get("correlation_id") ?? "";
  const [correlationId, setCorrelationId] = useState(urlCorrelationId);
  const [submittedId, setSubmittedId] = useState("");
  const [mode, setMode] = useState<"strict" | "re_execute">("strict");
  const [revisionId, setRevisionId] = useState("");

  useEffect(() => {
    if (urlCorrelationId) {
      setCorrelationId(urlCorrelationId);
      setSubmittedId(urlCorrelationId);
    }
  }, [urlCorrelationId]);

  const { data, isFetching, isSuccess, isError, error, refetch } = useQuery({
    queryKey: ["replay", submittedId, mode, revisionId],
    queryFn: () =>
      api.replay(submittedId, {
        mode,
        revision_id: revisionId || undefined,
      }),
    enabled: Boolean(submittedId),
    retry: false,
  });

  const graphTree = useMemo(
    () => buildGraphTree(data?.causal_graph, data?.timeline ?? []),
    [data?.causal_graph, data?.timeline],
  );

  const handleLoad = () => {
    if (!correlationId.trim()) return;
    setSubmittedId(correlationId.trim());
  };

  return (
    <div className="page-container">
      <PageHeader
        title="Forensic Replay"
        description="Inspect event chains or re-execute decisions with a different engine revision."
      />

      <ReplaySearchCard
        correlationId={correlationId}
        onCorrelationIdChange={setCorrelationId}
        mode={mode}
        onModeChange={setMode}
        revisionId={revisionId}
        onRevisionIdChange={setRevisionId}
        isFetching={isFetching}
        onLoad={handleLoad}
      />

      {isError ? (
        <ReplayErrorBanner error={error} onRetry={() => refetch()} />
      ) : null}

      {isFetching && !data ? (
        <div className="flex items-center justify-center gap-2 py-12 text-muted">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
          Loading timeline…
        </div>
      ) : null}

      {isSuccess && data?.feature_drift?.detected ? (
        <ReplayDriftBanner featureDrift={data.feature_drift} />
      ) : null}

      {isSuccess && data?.decision_diff ? (
        <ReplayDecisionDiffCard decisionDiff={data.decision_diff} />
      ) : null}

      {isSuccess && graphTree.length > 0 ? (
        <ReplayCausalGraphCard graphTree={graphTree} />
      ) : null}

      {isSuccess && data ? <ReplayTimelineCard data={data} /> : null}

      {!submittedId && !isFetching ? (
        <EmptyState
          message="No replay loaded"
          hint="Paste a correlation_id from Decision Monitor or Signals, then load the timeline"
        />
      ) : null}
    </div>
  );
}

export default function ReplayPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center p-12">
          <Loader2 className="h-6 w-6 animate-spin text-accent" />
        </div>
      }
    >
      <ReplayContent />
    </Suspense>
  );
}
