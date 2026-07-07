"use client";

import { usePathname } from "next/navigation";

const titles: Record<string, string> = {
  "/": "Decision Monitor",
  "/engine": "Engine Config",
  "/replay": "Forensic Replay",
  "/signals": "Signals",
  "/validation": "Validation Harness",
  "/providers": "Signal Providers",
};

export function TopBar() {
  const pathname = usePathname();
  const title =
    titles[pathname] ??
    (pathname.startsWith("/signals/") ? "Signal Detail" : "Dashboard");

  return (
    <div className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--background)]/70 px-6 py-4 backdrop-blur-md">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-widest text-muted">
          {title}
        </p>
        <div className="flex items-center gap-3 text-xs text-muted">
          <span className="hidden sm:inline">BTC/USDT · 1h</span>
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
