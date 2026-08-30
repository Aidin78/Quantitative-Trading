"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { ApiError, API_BASE, api } from "@/lib/api";

/**
 * Sticky banner shown when the backend is unreachable, so a down/misconfigured
 * API reads as "start the backend" instead of every page spinning forever.
 */
export function ApiHealthBanner() {
  const { error, isError } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: 15_000,
    retry: false,
  });

  const down = isError && error instanceof ApiError && error.connectivity;
  if (!down) return null;

  return (
    <div className="flex items-center gap-2 border-b border-danger/30 bg-[var(--danger-dim)] px-6 py-2 text-xs text-danger">
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
      <span>
        Can&apos;t reach the API at{" "}
        <span className="font-mono">{API_BASE}</span>. Start the backend:{" "}
        <span className="font-mono">
          cd backend &amp;&amp; poetry run uvicorn src.main:app --port 8000
        </span>
      </span>
    </div>
  );
}
