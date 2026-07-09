"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Power, Settings2 } from "lucide-react";
import { useState } from "react";
import { ProviderConfigModal } from "@/components/providers/ProviderConfigModal";
import { Badge, Card } from "@/components/ui/Card";
import { api, type ProviderConfig } from "@/lib/api";
import { requiredFeaturesForProvider } from "@/lib/providerMetadata";

type ProviderCardProps = {
  provider: ProviderConfig;
};

export function ProviderCard({ provider }: ProviderCardProps) {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const featureChips = requiredFeaturesForProvider(provider.provider_id);

  const toggle = useMutation({
    mutationFn: (enabled: boolean) =>
      api.patchProvider(provider.provider_id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["providers"] }),
  });

  return (
    <>
      <Card className="glass-card-hover">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-foreground">
              {provider.name ?? provider.provider_id.replace(/_/g, " ")}
            </h3>
            {provider.summary ? (
              <p className="mt-1 text-sm text-muted">{provider.summary}</p>
            ) : null}
            <div className="mt-2 flex flex-wrap gap-1">
              {featureChips.map((f) => (
                <span
                  key={f}
                  className="rounded bg-[var(--background)] px-2 py-0.5 font-mono text-[10px] text-muted"
                >
                  {f}
                </span>
              ))}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Badge variant={provider.enabled ? "success" : "default"} dot>
              {provider.enabled ? "enabled" : "disabled"}
            </Badge>
            <button
              type="button"
              className="btn-secondary text-xs"
              onClick={() => toggle.mutate(!provider.enabled)}
              disabled={toggle.isPending}
            >
              <Power className="h-3.5 w-3.5" />
              Toggle
            </button>
          </div>
        </div>

        <button
          type="button"
          className="btn-secondary mt-4 w-full text-xs"
          onClick={() => setModalOpen(true)}
        >
          <Settings2 className="h-3.5 w-3.5" />
          Logic &amp; parameters
        </button>
      </Card>

      <ProviderConfigModal
        provider={provider}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </>
  );
}
