"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Badge, Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function SignalsPage() {
  const { data } = useQuery({
    queryKey: ["signals"],
    queryFn: () => api.signals(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Signals</h1>
      <Card title="Approved Decisions">
        <div className="space-y-2">
          {data?.items.map((s) => (
            <Link
              key={s.id}
              href={`/signals/${s.id}`}
              className="flex items-center justify-between rounded border border-border p-3 hover:bg-background"
            >
              <div>
                <span className="font-medium">{s.symbol}</span>
                <span className="ml-2 text-sm text-muted">
                  {new Date(s.timestamp).toLocaleString()}
                </span>
              </div>
              <Badge variant="success">
                {s.side} {((s.confidence ?? 0) * 100).toFixed(0)}%
              </Badge>
            </Link>
          ))}
          {!data?.items.length && (
            <p className="text-sm text-muted">No approved signals</p>
          )}
        </div>
      </Card>
    </div>
  );
}
