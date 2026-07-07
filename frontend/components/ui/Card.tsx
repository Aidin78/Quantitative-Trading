export function Card({
  title,
  subtitle,
  children,
  className = "",
  noPadding = false,
}: {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  noPadding?: boolean;
}) {
  return (
    <div
      className={`glass-card animate-fade-in ${noPadding ? "" : "p-5"} ${className}`}
    >
      {title ? (
        <div className={`${noPadding ? "px-5 pt-5" : ""} mb-4`}>
          <h2 className="text-sm font-semibold tracking-wide text-foreground">
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-0.5 text-xs text-muted">{subtitle}</p>
          ) : null}
        </div>
      ) : null}
      <div className={noPadding && title ? "px-5 pb-5" : ""}>{children}</div>
    </div>
  );
}

export function Badge({
  children,
  variant = "default",
  dot = false,
}: {
  children: React.ReactNode;
  variant?: "default" | "success" | "danger" | "accent";
  dot?: boolean;
}) {
  const styles = {
    default: "bg-white/5 text-muted border border-[var(--border)]",
    success: "bg-[var(--success-dim)] text-success border border-success/20",
    danger: "bg-[var(--danger-dim)] text-danger border border-danger/20",
    accent: "bg-[var(--accent-dim)] text-accent border border-accent/20",
  };
  const dotColors = {
    default: "bg-muted",
    success: "bg-success",
    danger: "bg-danger",
    accent: "bg-accent",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[variant]}`}
    >
      {dot ? (
        <span
          className={`h-1.5 w-1.5 rounded-full ${dotColors[variant]} ${variant === "success" ? "animate-pulse-soft" : ""}`}
        />
      ) : null}
      {children}
    </span>
  );
}

export function StatCard({
  label,
  value,
  suffix,
  trend,
  icon,
}: {
  label: string;
  value: string | number;
  suffix?: string;
  trend?: "up" | "down" | "neutral";
  icon?: React.ReactNode;
}) {
  const trendColor = {
    up: "text-success",
    down: "text-danger",
    neutral: "text-muted",
  };
  return (
    <div className="glass-card-hover group p-5">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wider text-muted">
          {label}
        </p>
        {icon ? (
          <div className="rounded-lg bg-[var(--accent-dim)] p-2 text-accent opacity-80 transition-opacity group-hover:opacity-100">
            {icon}
          </div>
        ) : null}
      </div>
      <div className="mt-3 flex items-baseline gap-1">
        <span className="text-3xl font-semibold tracking-tight text-foreground">
          {value}
        </span>
        {suffix ? <span className="text-sm text-muted">{suffix}</span> : null}
      </div>
      {trend ? (
        <p className={`mt-1 text-xs ${trendColor[trend]}`}>
          {trend === "up" ? "↑" : trend === "down" ? "↓" : "—"} vs baseline
        </p>
      ) : null}
    </div>
  );
}

export function EmptyState({
  message,
  hint,
  className = "",
}: {
  message: string;
  hint?: string;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-lg border border-dashed border-[var(--border)] bg-[var(--background-elevated)]/50 py-12 text-center ${className}`}
    >
      <p className="text-sm text-muted">{message}</p>
      {hint ? <p className="mt-1 text-xs text-muted/70">{hint}</p> : null}
    </div>
  );
}
