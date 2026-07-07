"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cpu, Filter, Save, Shield } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
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
    <div className="page-container">
      <PageHeader
        title="Engine Config"
        description="Tune aggregation, market filter, and risk rules. Changes apply without redeploying providers."
        action={
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="btn-primary"
          >
            <Save className="h-4 w-4" />
            {mutation.isPending ? "Saving…" : "Save Changes"}
          </button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Risk Rules" subtitle="Pre-trade confidence thresholds">
          <div className="flex items-center gap-2 text-accent">
            <Shield className="h-4 w-4" />
          </div>
          <label className="mt-4 block text-xs font-medium uppercase tracking-wider text-muted">
            Min Confidence
          </label>
          <input
            className="input-field mt-2"
            value={minConfidence}
            onChange={(e) => setMinConfidence(e.target.value)}
          />
        </Card>

        <Card title="Aggregation" subtitle="Provider consensus rules">
          <div className="flex items-center gap-2 text-accent">
            <Cpu className="h-4 w-4" />
          </div>
          <label className="mt-4 block text-xs font-medium uppercase tracking-wider text-muted">
            Min Agreeing Providers
          </label>
          <input
            className="input-field mt-2"
            value={minAgreeing}
            onChange={(e) => setMinAgreeing(e.target.value)}
          />
        </Card>

        <Card title="Market Filter" subtitle="Volatility and session gates">
          <div className="flex items-center gap-2 text-accent">
            <Filter className="h-4 w-4" />
          </div>
          <label className="mt-4 block text-xs font-medium uppercase tracking-wider text-muted">
            Min ATR %
          </label>
          <input
            className="input-field mt-2"
            value={minAtrPct}
            onChange={(e) => setMinAtrPct(e.target.value)}
          />
        </Card>
      </div>

      <Card title="Current Configuration" subtitle="Live YAML snapshot">
        <pre className="overflow-auto rounded-lg bg-[var(--background)] p-4 font-mono text-xs leading-relaxed text-muted">
          {JSON.stringify(data?.engine, null, 2)}
        </pre>
      </Card>
    </div>
  );
}
