"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RotateCcw, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProviderCard } from "@/components/providers/ProviderCard";
import { EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function ProvidersPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.providers(),
  });

  const baseline = useMutation({
    mutationFn: () => api.applyProviderBaseline(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
  });

  const resetAll = useMutation({
    mutationFn: () => api.resetAllProviders(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
  });

  const busy = baseline.isPending || resetAll.isPending;

  return (
    <div className="page-container">
      <PageHeader
        title="Signal Providers"
        description="View each provider's signal logic, tune parameters, or reset to factory defaults."
        action={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-primary inline-flex items-center gap-2 text-sm"
              disabled={busy}
              onClick={() => baseline.mutate()}
            >
              {baseline.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Apply baseline
            </button>
            <button
              type="button"
              className="btn-secondary inline-flex items-center gap-2 text-sm"
              disabled={busy}
              onClick={() => resetAll.mutate()}
            >
              {resetAll.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RotateCcw className="h-4 w-4" />
              )}
              Reset all
            </button>
          </div>
        }
      />

      {(baseline.isError || resetAll.isError) && (
        <p className="mb-4 text-sm text-danger">
          {(baseline.error ?? resetAll.error)?.message ??
            "Failed to update providers"}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-muted lg:col-span-2">
            <Loader2 className="h-5 w-5 animate-spin text-accent" />
            Loading providers…
          </div>
        ) : isError ? (
          <div className="rounded-lg border border-danger/30 bg-[var(--danger-dim)] p-4 lg:col-span-2">
            <p className="font-medium text-danger">Failed to load providers</p>
            <p className="mt-1 text-sm text-muted">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
            <p className="mt-2 text-sm text-muted">
              Make sure the backend is running on{" "}
              <code className="text-foreground">localhost:8000</code> (or set{" "}
              <code className="text-foreground">NEXT_PUBLIC_API_URL</code>).
            </p>
            <button
              type="button"
              className="btn-secondary mt-3 text-sm"
              onClick={() => refetch()}
            >
              Retry
            </button>
          </div>
        ) : (
          data?.items.map((p) => (
            <ProviderCard key={p.provider_id} provider={p} />
          ))
        )}
        {!isLoading && !isError && !data?.items.length && (
          <EmptyState
            message="No providers configured"
            className="lg:col-span-2"
          />
        )}
      </div>
    </div>
  );
}
