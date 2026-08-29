"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Beaker,
  CheckCircle2,
  Loader2,
  Plus,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionTabs } from "@/components/layout/SectionTabs";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type {
  Candidate,
  CandidateState,
  Hypothesis,
  HypothesisStatus,
} from "@/lib/api/types";

const HYPOTHESIS_BADGE: Record<
  HypothesisStatus,
  "default" | "success" | "danger" | "accent" | "warning"
> = {
  open: "default",
  tested: "accent",
  confirmed: "success",
  rejected: "danger",
};

const CANDIDATE_BADGE: Record<
  CandidateState,
  "default" | "success" | "danger" | "accent" | "warning"
> = {
  candidate: "default",
  challenger: "accent",
  champion: "success",
  rejected: "danger",
  archived: "default",
};

const PROMOTION_TARGETS: Record<CandidateState, CandidateState[]> = {
  candidate: ["challenger", "rejected", "archived"],
  challenger: ["champion", "rejected", "archived"],
  champion: ["archived"],
  rejected: ["archived"],
  archived: [],
};

export default function ResearchPage() {
  return (
    <div className="page-container">
      <PageHeader
        title="Research"
        description="Structured hypotheses, experiment memory, and the candidate promotion lifecycle — the self-improving research loop layered on top of the Decision Engine."
      />
      <SectionTabs
        tabs={[
          { href: "/research", label: "Hypotheses & Candidates" },
          { href: "/experiments", label: "Experiments" },
        ]}
      />
      <HypothesesSection />
      <CandidatesSection />
    </div>
  );
}

function HypothesesSection() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [runId, setRunId] = useState("");
  const [genJobId, setGenJobId] = useState<string | null>(null);
  const [genError, setGenError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["hypotheses"],
    queryFn: () => api.hypotheses({ limit: 50 }),
  });

  const generate = useMutation({
    mutationFn: (id: string) => api.generateHypothesis(id),
    onSuccess: (result) => {
      setGenError(null);
      setGenJobId(result.job_id);
    },
    onError: (err) => {
      setGenError(
        err instanceof Error ? err.message : "Generation failed to start",
      );
    },
  });

  const { data: jobStatus } = useQuery({
    queryKey: ["hypothesis-generation-job", genJobId],
    queryFn: () => api.hypothesisGenerationJob(genJobId as string),
    enabled: !!genJobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 800;
    },
  });

  useEffect(() => {
    if (jobStatus?.status === "completed") {
      queryClient.invalidateQueries({ queryKey: ["hypotheses"] });
    }
  }, [jobStatus?.status, queryClient]);

  const items = data?.items ?? [];

  const resolve = useMutation({
    mutationFn: ({ id, confirmed }: { id: string; confirmed: boolean }) =>
      api.resolveHypothesis(id, confirmed),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["hypotheses"] }),
  });

  return (
    <Card
      title="Hypotheses"
      subtitle="Observation → Statement → Expected Effect → Proposed Change"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
            placeholder="run_id to draft from (e.g. run_abc123)"
            className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] px-3 py-1.5 text-xs text-foreground placeholder:text-muted/60 focus:border-accent focus:outline-none"
          />
          <button
            type="button"
            onClick={() => runId && generate.mutate(runId)}
            disabled={
              !runId || generate.isPending || jobStatus?.status === "running"
            }
            className="btn-secondary text-xs"
          >
            {generate.isPending || jobStatus?.status === "running" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            Draft with LLM
          </button>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate((v) => !v)}
          className="btn-secondary text-xs"
        >
          <Plus className="h-3.5 w-3.5" />
          New hypothesis
        </button>
      </div>

      {genError ? (
        <p className="mb-3 rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-xs text-danger">
          {genError}
        </p>
      ) : null}
      {jobStatus?.status === "failed" ? (
        <p className="mb-3 rounded-lg border border-danger/20 bg-[var(--danger-dim)] p-3 text-xs text-danger">
          Generation failed: {jobStatus.error}
        </p>
      ) : null}
      {jobStatus?.status === "completed" ? (
        <p className="mb-3 rounded-lg border border-success/20 bg-[var(--success-dim)] p-3 text-xs text-success">
          Draft generated and added below (created_by: llm) — still a plain open
          hypothesis pending human review.
        </p>
      ) : null}

      {showCreate ? (
        <CreateHypothesisForm onDone={() => setShowCreate(false)} />
      ) : null}

      {isLoading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
        </div>
      ) : !items.length ? (
        <EmptyState
          message="No hypotheses yet"
          hint="Draft one from a backtest run's failure summary, or add one manually"
        />
      ) : (
        <div className="space-y-3">
          {items.map((h) => (
            <HypothesisRow
              key={h.hypothesis_id}
              hypothesis={h}
              onResolve={(confirmed) =>
                resolve.mutate({ id: h.hypothesis_id, confirmed })
              }
              resolving={resolve.isPending}
            />
          ))}
        </div>
      )}
    </Card>
  );
}

function HypothesisRow({
  hypothesis,
  onResolve,
  resolving,
}: {
  hypothesis: Hypothesis;
  onResolve: (confirmed: boolean) => void;
  resolving: boolean;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Beaker className="h-4 w-4 shrink-0 text-accent" />
            <Badge variant={HYPOTHESIS_BADGE[hypothesis.status]}>
              {hypothesis.status}
            </Badge>
            {hypothesis.created_by === "llm" ? (
              <Badge variant="accent">
                <Sparkles className="h-3 w-3" /> llm
              </Badge>
            ) : null}
            <span className="font-mono text-xs text-muted">
              {hypothesis.hypothesis_id}
            </span>
          </div>
          <p className="mt-2 text-sm text-foreground/90">
            {hypothesis.statement}
          </p>
          <div className="mt-2 grid gap-1.5 text-xs text-muted sm:grid-cols-2">
            <p>
              <span className="text-foreground/70">Observation:</span>{" "}
              {hypothesis.observation}
            </p>
            <p>
              <span className="text-foreground/70">Expected effect:</span>{" "}
              {hypothesis.expected_effect}
            </p>
            <p className="sm:col-span-2">
              <span className="text-foreground/70">Proposed change:</span>{" "}
              {hypothesis.proposed_change}
            </p>
          </div>
        </div>
        {hypothesis.status === "tested" ? (
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={() => onResolve(true)}
              disabled={resolving}
              className="btn-secondary border-success/30 px-2.5 py-1.5 text-xs text-success hover:border-success/50"
            >
              <CheckCircle2 className="h-3.5 w-3.5" /> Confirm
            </button>
            <button
              type="button"
              onClick={() => onResolve(false)}
              disabled={resolving}
              className="btn-secondary border-danger/30 px-2.5 py-1.5 text-xs text-danger hover:border-danger/50"
            >
              <XCircle className="h-3.5 w-3.5" /> Reject
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function CreateHypothesisForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [observation, setObservation] = useState("");
  const [statement, setStatement] = useState("");
  const [expectedEffect, setExpectedEffect] = useState("");
  const [proposedChange, setProposedChange] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.createHypothesis({
        observation,
        statement,
        expected_effect: expectedEffect,
        proposed_change: proposedChange,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hypotheses"] });
      onDone();
    },
  });

  const canSubmit =
    observation.trim() &&
    statement.trim() &&
    expectedEffect.trim() &&
    proposedChange.trim();

  return (
    <div className="mb-4 space-y-2 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-4">
      <textarea
        value={observation}
        onChange={(e) => setObservation(e.target.value)}
        placeholder="Observation — what did the failure analysis show?"
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-foreground placeholder:text-muted/60 focus:border-accent focus:outline-none"
        rows={2}
      />
      <textarea
        value={statement}
        onChange={(e) => setStatement(e.target.value)}
        placeholder="Statement — the general claim behind it"
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-foreground placeholder:text-muted/60 focus:border-accent focus:outline-none"
        rows={2}
      />
      <textarea
        value={expectedEffect}
        onChange={(e) => setExpectedEffect(e.target.value)}
        placeholder="Expected effect — what should improve if it's true"
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-foreground placeholder:text-muted/60 focus:border-accent focus:outline-none"
        rows={2}
      />
      <textarea
        value={proposedChange}
        onChange={(e) => setProposedChange(e.target.value)}
        placeholder="Proposed change — the concrete config/provider change to test"
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-foreground placeholder:text-muted/60 focus:border-accent focus:outline-none"
        rows={2}
      />
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onDone}
          className="btn-secondary text-xs"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => create.mutate()}
          disabled={!canSubmit || create.isPending}
          className="btn-primary text-xs"
        >
          {create.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : null}
          Save hypothesis
        </button>
      </div>
    </div>
  );
}

function CandidatesSection() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["candidates"],
    queryFn: () => api.candidates({ limit: 50 }),
  });

  const promote = useMutation({
    mutationFn: ({ id, to_state }: { id: string; to_state: string }) =>
      api.promoteCandidate(id, to_state),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["candidates"] }),
  });

  const items = data?.items ?? [];

  return (
    <Card
      title="Candidates"
      subtitle="candidate → challenger → champion — deterministic acceptance policy, no LLM in the promotion decision"
    >
      {isLoading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
        </div>
      ) : !items.length ? (
        <EmptyState
          message="No candidates yet"
          hint="Candidates are created from an experiment + optional hypothesis, then evaluated against out-of-sample validity, sample size, fold stability, and regime concentration"
        />
      ) : (
        <div className="space-y-3">
          {items.map((c) => (
            <CandidateRow
              key={c.candidate_id}
              candidate={c}
              onPromote={(to_state) =>
                promote.mutate({ id: c.candidate_id, to_state })
              }
              promoting={promote.isPending}
            />
          ))}
        </div>
      )}
    </Card>
  );
}

function CandidateRow({
  candidate,
  onPromote,
  promoting,
}: {
  candidate: Candidate;
  onPromote: (toState: string) => void;
  promoting: boolean;
}) {
  const { data: evaluations } = useQuery({
    queryKey: ["candidate-evaluations", candidate.candidate_id],
    queryFn: () => api.candidateEvaluations(candidate.candidate_id),
  });
  const latest = evaluations?.items?.[evaluations.items.length - 1];
  const targets = PROMOTION_TARGETS[candidate.state];

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <ArrowUpRight className="h-4 w-4 shrink-0 text-accent" />
            <Badge variant={CANDIDATE_BADGE[candidate.state]}>
              {candidate.state}
            </Badge>
            <span className="font-mono text-xs text-muted">
              {candidate.candidate_id}
            </span>
          </div>
          <div className="mt-2 grid gap-1.5 text-xs text-muted sm:grid-cols-2">
            <p>
              <span className="text-foreground/70">Experiment:</span>{" "}
              <span className="font-mono">{candidate.experiment_id}</span>
            </p>
            {candidate.hypothesis_id ? (
              <p>
                <span className="text-foreground/70">Hypothesis:</span>{" "}
                <span className="font-mono">{candidate.hypothesis_id}</span>
              </p>
            ) : null}
          </div>
          {latest ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {latest.checks.map((check) => (
                <Badge
                  key={check.name}
                  variant={check.passed ? "success" : "danger"}
                >
                  {check.passed ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : (
                    <XCircle className="h-3 w-3" />
                  )}
                  {check.name}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
        {targets.length ? (
          <div className="flex shrink-0 flex-wrap gap-2">
            {targets.map((target) => (
              <button
                key={target}
                type="button"
                onClick={() => onPromote(target)}
                disabled={promoting}
                className="btn-secondary text-xs"
              >
                {promoting ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : null}
                → {target}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
