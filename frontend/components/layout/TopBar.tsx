"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";

const titles: Record<string, string> = {
  "/": "Decision Monitor",
  "/engine": "Engine Config",
  "/replay": "Forensic Replay",
  "/signals": "Signals",
  "/validation": "Validation Harness",
  "/optimization": "Auto Optimizer",
  "/providers": "Signal Providers",
};

export function TopBar() {
  const pathname = usePathname();
  const title =
    titles[pathname] ??
    (pathname.startsWith("/signals/") ? "Signal Detail" : "Dashboard");

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: 60_000,
  });

  const { data: decisions } = useQuery({
    queryKey: ["decisions", "topbar"],
    queryFn: () => api.decisions("limit=1"),
    refetchInterval: 30_000,
  });

  const latest = decisions?.items[0];
  const symbol = latest?.symbol ?? health?.default_symbol;
  const timeframe = latest?.timeframe ?? health?.default_timeframe;
  const marketLabel =
    symbol && timeframe ? `${symbol} · ${timeframe}` : "No market context";

  return (
    <div className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--background)]/70 px-6 py-4 backdrop-blur-md">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-widest text-muted">
          {title}
        </p>
        <div className="flex items-center gap-3 text-xs text-muted">
          <span className="hidden sm:inline font-mono">{marketLabel}</span>
          <span className="h-1 w-1 rounded-full bg-[var(--border-strong)]" />
          <span>
            {new Date().toLocaleDateString(undefined, {
              weekday: "short",
              month: "short",
              day: "numeric",
            })}
          </span>
        </div>
      </div>
    </div>
  );
}
