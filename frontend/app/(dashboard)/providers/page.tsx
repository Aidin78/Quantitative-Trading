"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProviderCard } from "@/components/providers/ProviderCard";
import { EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function ProvidersPage() {
  const { data } = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.providers(),
  });

  return (
    <div className="page-container">
      <PageHeader
        title="Signal Providers"
        description="View each provider's signal logic, tune parameters, or reset to factory defaults."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        {data?.items.map((p) => (
          <ProviderCard key={p.provider_id} provider={p} />
        ))}
        {!data?.items.length && (
          <EmptyState
            message="No providers configured"
            className="lg:col-span-2"
          />
        )}
      </div>
    </div>
  );
}
