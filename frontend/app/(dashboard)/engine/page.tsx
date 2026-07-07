"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function EngineConfigPage() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["engine-config"],
    queryFn: () => api.engineConfig(),
  });
  const [minConfidence, setMinConfidence] = useState("0.65");
  const [minAgreeing, setMinAgreeing] = useState("2");
  const [minAtrPct, setMinAtrPct] = useState("0.3");

  useEffect(() => {
    const engine = data?.engine;
    if (!engine) return;
    const risk = engine.risk as { min_confidence?: number };
    const agg = engine.aggregation as { min_agreeing_providers?: number };
    const filt = engine.filter as { min_atr_pct?: number };
    if (risk.min_confidence != null)
      setMinConfidence(String(risk.min_confidence));
    if (agg.min_agreeing_providers != null)
      setMinAgreeing(String(agg.min_agreeing_providers));
    if (filt.min_atr_pct != null) setMinAtrPct(String(filt.min_atr_pct));
  }, [data]);

  const mutation = useMutation({
    mutationFn: () =>
      api.patchEngineConfig({
        risk: { min_confidence: parseFloat(minConfidence) },
        aggregation: { min_agreeing_providers: parseInt(minAgreeing, 10) },
        filter: { min_atr_pct: parseFloat(minAtrPct) },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["engine-config"] }),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Engine Config</h1>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Risk Rules">
          <label className="block text-sm text-muted">Min Confidence</label>
          <input
            className="mt-1 w-full rounded border border-border bg-background px-3 py-2"
            value={minConfidence}
            onChange={(e) => setMinConfidence(e.target.value)}
          />
        </Card>
        <Card title="Aggregation">
          <label className="block text-sm text-muted">
            Min Agreeing Providers
          </label>
          <input
            className="mt-1 w-full rounded border border-border bg-background px-3 py-2"
            value={minAgreeing}
            onChange={(e) => setMinAgreeing(e.target.value)}
          />
        </Card>
        <Card title="Market Filter">
          <label className="block text-sm text-muted">Min ATR %</label>
          <input
            className="mt-1 w-full rounded border border-border bg-background px-3 py-2"
            value={minAtrPct}
            onChange={(e) => setMinAtrPct(e.target.value)}
          />
        </Card>
      </div>
      <button
        type="button"
        onClick={() => mutation.mutate()}
        className="rounded bg-accent px-4 py-2 text-sm text-white"
      >
        Save Config
      </button>
      <Card title="Current Config">
        <pre className="overflow-auto text-xs">
          {JSON.stringify(data?.engine, null, 2)}
        </pre>
      </Card>
    </div>
  );
}
