export function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-lg border border-border bg-card p-4 ${className}`}>
      {title ? (
        <h2 className="mb-3 text-sm font-medium text-muted">{title}</h2>
      ) : null}
      {children}
    </div>
  );
}

export function Badge({
  children,
  variant = "default",
}: {
  children: React.ReactNode;
  variant?: "default" | "success" | "danger";
}) {
  const colors = {
    default: "bg-border text-foreground",
    success: "bg-success/20 text-success",
    danger: "bg-danger/20 text-danger",
  };
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${colors[variant]}`}
    >
      {children}
    </span>
  );
}
