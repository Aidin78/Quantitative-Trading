"use client";

import { useQuery } from "@tanstack/react-query";
import { FlaskConical, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Card, EmptyState } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function ExperimentsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["experiments"],
    queryFn: () => api.experiments(),
  });

  return (
    <div className="page-container">
      <PageHeader
        title="Experiments"
        description="Tracked validation and live runs bound to config revisions."
      />

      <Card title="Experiment Registry" subtitle="Governance-bound runs">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-accent" />
          </div>
        ) : !data?.items.length ? (
          <EmptyState
            message="No experiments yet"
            hint="Run validation from the dashboard to create one automatically"
          />
        ) : (
          <div className="space-y-3">
            {data.items.map((exp) => (
              <div
                key={exp.experiment_id}
                className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <FlaskConical className="h-4 w-4 text-accent" />
                    <p className="font-medium text-foreground">{exp.name}</p>
                  </div>
                  <Badge variant="accent">{exp.status}</Badge>
                </div>
                <div className="mt-3 grid gap-2 text-xs text-muted sm:grid-cols-2">
                  <p>
                    <span className="text-foreground/70">ID:</span>{" "}
                    <span className="font-mono">{exp.experiment_id}</span>
                  </p>
                  <p>
                    <span className="text-foreground/70">Revision:</span>{" "}
                    <span className="font-mono">{exp.revision_id}</span>
                  </p>
                  <p>
                    <span className="text-foreground/70">Mode:</span> {exp.mode}
                  </p>
                  <p>
                    <span className="text-foreground/70">Symbols:</span>{" "}
                    {exp.symbols.join(", ")}
                  </p>
                </div>
                {exp.hypothesis ? (
                  <p className="mt-2 text-sm text-foreground/80">
                    {exp.hypothesis}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
