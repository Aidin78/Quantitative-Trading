"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Power } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function ProvidersPage() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.providers(),
  });

  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patchProvider(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["providers"] }),
  });

  return (
    <div className="page-container">
      <PageHeader
        title="Signal Providers"
        description="Plug-in strategies that interpret features — enable, disable, and tune weights."
      />

      <div className="grid gap-4 md:grid-cols-2">
        {data?.items.map((p) => (
          <Card key={p.provider_id} className="glass-card-hover">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--accent-dim)] text-accent">
                  <Layers className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">
                    {p.provider_id.replace(/_/g, " ")}
                  </h3>
                  <p className="mt-0.5 text-xs text-muted">
                    weight: {p.weight}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {(
                      p as { required_features?: string[] }
                    ).required_features?.map((f) => (
                      <span
                        key={f}
                        className="rounded bg-[var(--background)] px-2 py-0.5 font-mono text-[10px] text-muted"
                      >
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-end gap-2">
                <Badge variant={p.enabled ? "success" : "default"} dot>
                  {p.enabled ? "enabled" : "disabled"}
                </Badge>
                <button
                  type="button"
                  className="btn-secondary text-xs"
                  onClick={() =>
                    toggle.mutate({ id: p.provider_id, enabled: !p.enabled })
                  }
                >
                  <Power className="h-3.5 w-3.5" />
                  Toggle
                </button>
              </div>
            </div>
          </Card>
        ))}
        {!data?.items.length && (
          <EmptyState
            message="No providers configured"
            className="md:col-span-2"
          />
        )}
      </div>
    </div>
  );
}
