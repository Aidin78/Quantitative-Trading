import { APP_VERSION, COPYRIGHT, DEVELOPER } from "@/lib/app-info";

type AppFooterProps = {
  variant?: "bar" | "compact" | "full";
};

export function AppFooter({ variant = "bar" }: AppFooterProps) {
  if (variant === "compact") {
    return (
      <p className="text-center text-[10px] text-muted">
        v{APP_VERSION} · {DEVELOPER}
      </p>
    );
  }

  if (variant === "full") {
    return (
      <div className="space-y-1 text-center text-xs text-muted">
        <p>
          Developed by <span className="text-foreground">{DEVELOPER}</span>
        </p>
        <p className="font-mono text-[11px]">v{APP_VERSION}</p>
        <p className="text-[10px]">{COPYRIGHT}</p>
      </div>
    );
  }

  return (
    <footer className="border-t border-[var(--border)] bg-[var(--background-elevated)]/60 px-6 py-3 backdrop-blur-md lg:px-8">
      <div className="flex flex-col items-center justify-between gap-2 text-xs text-muted sm:flex-row">
        <p>{COPYRIGHT}</p>
        <div className="flex items-center gap-3">
          <span>
            Developed by <span className="text-foreground/90">{DEVELOPER}</span>
          </span>
          <span className="h-1 w-1 rounded-full bg-[var(--border-strong)]" />
          <span className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-0.5 font-mono text-[10px]">
            v{APP_VERSION}
          </span>
        </div>
      </div>
    </footer>
  );
}
