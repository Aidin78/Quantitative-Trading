"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

function ReplayContent() {
  const params = useSearchParams();
  const [correlationId, setCorrelationId] = useState(
    params.get("correlation_id") ?? "",
  );

  const { data, refetch, isFetching } = useQuery({
    queryKey: ["replay", correlationId],
    queryFn: () => api.replay(correlationId),
    enabled: false,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Forensic Replay</h1>
      <Card title="Cycle Search">
        <input
          className="w-full rounded border border-border bg-background px-3 py-2"
          value={correlationId}
          onChange={(e) => setCorrelationId(e.target.value)}
          placeholder="correlation_id"
        />
        <button
          type="button"
          onClick={() => refetch()}
          disabled={!correlationId || isFetching}
          className="mt-3 rounded bg-accent px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          Load Timeline
        </button>
      </Card>
      {data?.timeline && (
        <Card title="Timeline">
          <div className="space-y-2">
            {data.timeline.map((entry, i) => (
              <div key={i} className="rounded bg-background p-2 text-sm">
                <span className="text-muted">
                  {String(entry.event_time ?? "")}
                </span>{" "}
                — {String(entry.event_type ?? "")}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

export default function ReplayPage() {
  return (
    <Suspense fallback={<p className="text-muted">Loading...</p>}>
      <ReplayContent />
    </Suspense>
  );
}
