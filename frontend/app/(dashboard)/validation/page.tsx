"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function ValidationPage() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [startDate, setStartDate] = useState("2026-01-01");

  const run = useMutation({
    mutationFn: () =>
      api.runValidation({ symbol, start_date: startDate, timeframe: "1h" }),
    onSuccess: (res) => setJobId(res.id),
  });

  const { data: job } = useQuery({
    queryKey: ["validation", jobId],
    queryFn: () => api.validation(jobId!),
    enabled: !!jobId,
    refetchInterval: (q) =>
      q.state.data?.status === "completed" ? false : 2000,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Validation</h1>
      <Card title="Run Harness">
        <div className="grid gap-3 md:grid-cols-2">
          <input
            className="rounded border border-border bg-background px-3 py-2"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="Symbol"
          />
          <input
            className="rounded border border-border bg-background px-3 py-2"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            placeholder="Start date"
          />
        </div>
        <button
          type="button"
          onClick={() => run.mutate()}
          className="mt-3 rounded bg-accent px-4 py-2 text-sm text-white"
        >
          Run Validation
        </button>
      </Card>
      {job && (
        <Card title={`Job ${job.id}`}>
          <p className="text-sm">Status: {job.status}</p>
          {job.engine_metrics && (
            <pre className="mt-3 overflow-auto text-xs">
              {JSON.stringify(job.engine_metrics, null, 2)}
            </pre>
          )}
          {job.outcome_metrics && (
            <pre className="mt-3 overflow-auto text-xs">
              {JSON.stringify(job.outcome_metrics, null, 2)}
            </pre>
          )}
          {job.error && <p className="mt-2 text-sm text-danger">{job.error}</p>}
        </Card>
      )}
    </div>
  );
}
