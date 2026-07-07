"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Card } from "@/components/ui/Card";
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
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Providers</h1>
      <div className="grid gap-3">
        {data?.items.map((p) => (
          <Card key={p.provider_id}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-medium">{p.provider_id}</h3>
                <p className="text-xs text-muted">weight: {p.weight}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={p.enabled ? "success" : "default"}>
                  {p.enabled ? "enabled" : "disabled"}
                </Badge>
                <button
                  type="button"
                  className="rounded border border-border px-3 py-1 text-xs"
                  onClick={() =>
                    toggle.mutate({ id: p.provider_id, enabled: !p.enabled })
                  }
                >
                  Toggle
                </button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
