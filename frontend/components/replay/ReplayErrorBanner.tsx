"use client";

import { AlertTriangle } from "lucide-react";
import { parseErrorMessage } from "@/components/replay/parseErrorMessage";

type Props = {
  error: unknown;
  onRetry: () => void;
};

export function ReplayErrorBanner({ error, onRetry }: Props) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-danger/30 bg-[var(--danger-dim)] p-4">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
      <div>
        <p className="font-medium text-danger">Replay failed</p>
        <p className="mt-1 text-sm text-muted">{parseErrorMessage(error)}</p>
        <button
          type="button"
          className="btn-secondary mt-3 text-xs"
          onClick={onRetry}
        >
          Retry
        </button>
      </div>
    </div>
  );
}
