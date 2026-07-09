"use client";

import { CircleHelp } from "lucide-react";

type Props = {
  label: string;
  tooltip: string;
  htmlFor?: string;
  className?: string;
};

export function FieldLabel({ label, tooltip, htmlFor, className }: Props) {
  return (
    <div className={`flex items-center gap-1.5 ${className ?? ""}`}>
      <label
        htmlFor={htmlFor}
        className="text-xs font-medium uppercase tracking-wider text-muted"
      >
        {label}
      </label>
      <span className="group relative inline-flex shrink-0">
        <button
          type="button"
          tabIndex={-1}
          className="inline-flex rounded text-muted transition-colors hover:text-foreground focus-visible:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
          aria-label={`${label}: ${tooltip}`}
        >
          <CircleHelp className="h-3.5 w-3.5" />
        </button>
        <span
          role="tooltip"
          className="pointer-events-none absolute bottom-[calc(100%+6px)] left-1/2 z-50 hidden w-56 -translate-x-1/2 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] px-3 py-2 text-left text-xs font-normal normal-case tracking-normal leading-relaxed text-foreground shadow-lg group-hover:block group-focus-within:block"
        >
          {tooltip}
        </span>
      </span>
    </div>
  );
}

type CheckboxFieldProps = {
  label: string;
  tooltip: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  className?: string;
};

export function CheckboxField({
  label,
  tooltip,
  checked,
  onChange,
  className,
}: CheckboxFieldProps) {
  return (
    <label
      className={`flex cursor-pointer items-center gap-2 text-sm text-muted ${className ?? ""}`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{label}</span>
      <span className="group relative inline-flex shrink-0">
        <button
          type="button"
          tabIndex={-1}
          className="inline-flex rounded text-muted transition-colors hover:text-foreground"
          aria-label={`${label}: ${tooltip}`}
          onClick={(e) => e.preventDefault()}
        >
          <CircleHelp className="h-3.5 w-3.5" />
        </button>
        <span
          role="tooltip"
          className="pointer-events-none absolute bottom-[calc(100%+6px)] left-1/2 z-50 hidden w-56 -translate-x-1/2 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] px-3 py-2 text-left text-xs font-normal normal-case tracking-normal leading-relaxed text-foreground shadow-lg group-hover:block group-focus-within:block"
        >
          {tooltip}
        </span>
      </span>
    </label>
  );
}
