"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pause, Play, Radio } from "lucide-react";
import { Badge, Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

export function LiveStatusCard() {
  const qc = useQueryClient();
  const { data: live, isLoading } = useQuery({
    queryKey: ["live-status"],
    queryFn: () => api.liveStatus(),
    refetchInterval: 10_000,
  });

  const start = useMutation({
    mutationFn: () => api.startLive({ mode: live?.mode ?? "paper" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["live-status"] }),
  });

  const stop = useMutation({
    mutationFn: () => api.stopLive(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["live-status"] }),
  });

  const setMode = useMutation({
    mutationFn: (mode: "paper" | "live") => api.setLiveMode(mode),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["live-status"] }),
  });

  if (isLoading && !live) {
    return (
      <Card title="Live Engine" subtitle="Paper / live runtime">
        <div className="flex items-center justify-center py-6">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
        </div>
      </Card>
    );
  }

  const status = live?.status ?? "stopped";
  const statusVariant =
    status === "running"
      ? "success"
      : status === "paused"
        ? "warning"
        : "default";

  return (
    <Card title="Live Engine" subtitle="Scheduler and exchange connectivity">
      <div className="space-y-4">
        <div className="flex justify-end">
          <Badge variant={statusVariant} dot>
            {status}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3">
            <p className="text-xs text-muted">Mode</p>
            <p className="mt-1 font-medium capitalize">
              {live?.mode ?? "paper"}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3">
            <p className="text-xs text-muted">Exchange</p>
            <p className="mt-1 font-medium">
              {live?.exchange_connected ? "Connected" : "Offline"}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3">
            <p className="text-xs text-muted">Alerts (Telegram)</p>
            <p className="mt-1 font-medium">
              {live?.alerts_connected ? "Connected" : "—"}
            </p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)]/50 p-3">
            <p className="text-xs text-muted">Last run</p>
            <p className="mt-1 font-mono text-xs">
              {live?.last_run_at
                ? new Date(live.last_run_at).toLocaleString()
                : "—"}
            </p>
          </div>
        </div>

        {live?.last_error ? (
          <p className="rounded-lg border border-danger/20 bg-[var(--danger-dim)] px-3 py-2 text-xs text-danger">
            {live.last_error}
          </p>
        ) : null}

        {live?.jobs?.length ? (
          <div className="space-y-1 text-xs text-muted">
            {live.jobs.map((job) => (
              <div
                key={`${job.symbol}-${job.timeframe}`}
                className="flex justify-between"
              >
                <span className="font-mono">
                  {job.symbol} · {job.timeframe}
                </span>
                <span>
                  {job.next_run_at
                    ? new Date(job.next_run_at).toLocaleString()
                    : "—"}
                </span>
              </div>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {status !== "running" ? (
            <button
              type="button"
              onClick={() => start.mutate()}
              disabled={start.isPending}
              className="btn-primary"
            >
              {start.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Start
            </button>
          ) : (
            <button
              type="button"
              onClick={() => stop.mutate()}
              disabled={stop.isPending}
              className="btn-secondary"
            >
              {stop.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Pause className="h-4 w-4" />
              )}
              Stop
            </button>
          )}
          <button
            type="button"
            onClick={() =>
              setMode.mutate(live?.mode === "paper" ? "live" : "paper")
            }
            disabled={setMode.isPending}
            className="btn-secondary"
          >
            <Radio className="h-4 w-4" />
            {live?.mode === "paper" ? "Switch to Live" : "Switch to Paper"}
          </button>
        </div>
      </div>
    </Card>
  );
}
