"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Decision Monitor" },
  { href: "/engine", label: "Engine Config" },
  { href: "/replay", label: "Replay" },
  { href: "/signals", label: "Signals" },
  { href: "/validation", label: "Validation" },
  { href: "/providers", label: "Providers" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-border bg-card p-4 min-h-screen">
      <div className="mb-8">
        <h1 className="text-lg font-semibold text-accent">Trading Platform</h1>
        <p className="text-xs text-muted">Decision Engine Monitor</p>
      </div>
      <nav className="flex flex-col gap-1">
        {links.map((link) => {
          const active = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`rounded px-3 py-2 text-sm ${
                active
                  ? "bg-accent/20 text-accent"
                  : "text-muted hover:text-foreground"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
