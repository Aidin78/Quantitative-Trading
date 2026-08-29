"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Beaker,
  Cpu,
  GitBranch,
  Layers,
  Database,
  Loader2,
  PlayCircle,
  Wallet,
  Zap,
} from "lucide-react";
import { APP_NAME } from "@/lib/app-info";
import { useActiveOptimizationSweep } from "@/contexts/OptimizationSweepContext";

// Validation covers the Backtest + Optimize tabs; Research covers the
// Hypotheses/Candidates + Experiments tabs — see components/layout/SectionTabs.
type NavLink = {
  href: string;
  label: string;
  icon: typeof Activity;
  aliases?: string[];
};

const sections: { heading: string; links: NavLink[] }[] = [
  {
    heading: "Trading",
    links: [
      { href: "/portfolio", label: "Book", icon: Wallet },
      { href: "/", label: "Decision Monitor", icon: Activity },
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
    ],
  },
  {
    heading: "Research",
    links: [
      {
        href: "/validation",
        label: "Validation",
        icon: PlayCircle,
        aliases: ["/optimization"],
      },
      {
        href: "/research",
        label: "Research",
        icon: Beaker,
        aliases: ["/experiments"],
      },
      { href: "/providers", label: "Providers", icon: Layers },
      { href: "/engine", label: "Engine Config", icon: Cpu },
      { href: "/market-data", label: "Market Data", icon: Database },
      { href: "/replay", label: "Replay", icon: GitBranch },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isActive: optimizationRunning, sweepId } =
    useActiveOptimizationSweep();
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--background-elevated)]/80 backdrop-blur-xl">
      <div className="border-b border-[var(--border)] p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-emerald-500 shadow-lg shadow-accent/20">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-tight text-foreground">
              {APP_NAME}
            </h1>
            <p className="text-[11px] text-muted">Decision-centric platform</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-5 p-3">
        {sections.map((section) => (
          <div key={section.heading} className="space-y-1">
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted/60">
              {section.heading}
            </p>
            {section.links.map((link) => {
              const aliases = link.aliases ?? [];
              const active =
                pathname === link.href ||
                (link.href !== "/" && pathname.startsWith(link.href)) ||
                aliases.some((a) => pathname.startsWith(a));
              const Icon = link.icon;
              // a running sweep lives under the Validation section (Optimize tab)
              const showOptimizerPulse =
                link.href === "/validation" && optimizationRunning;
              return (
                <Link
                  key={link.href}
                  href={
                    link.href === "/validation" && sweepId
                      ? `/optimization?sweep=${encodeURIComponent(sweepId)}`
                      : link.href
                  }
                  className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
                    active
                      ? "bg-[var(--accent-dim)] text-accent shadow-sm"
                      : "text-muted hover:bg-white/5 hover:text-foreground"
                  }`}
                >
                  <Icon
                    className={`h-4 w-4 shrink-0 ${active ? "text-accent" : "text-muted group-hover:text-foreground"}`}
                  />
                  {link.label}
                  {showOptimizerPulse ? (
                    <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-accent" />
                  ) : active ? (
                    <span className="ml-auto h-1.5 w-1.5 rounded-full bg-accent shadow-[0_0_8px_var(--glow)]" />
                  ) : null}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}
