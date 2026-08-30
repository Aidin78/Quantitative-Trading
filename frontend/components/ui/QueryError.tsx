import { ApiError } from "@/lib/api";

/** Inline error box for a failed useQuery — distinguishes "backend down" from
 * a real API error, with a retry button. */
export function QueryError({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  const connectivity = error instanceof ApiError && error.connectivity;
  const message =
    error instanceof Error ? error.message : "Something went wrong";
  return (
    <div className="rounded-lg border border-danger/30 bg-[var(--danger-dim)] p-4">
      <p className="font-medium text-danger">
        {connectivity ? "Backend unreachable" : "Failed to load"}
      </p>
      <p className="mt-1 text-sm text-muted">{message}</p>
      {onRetry ? (
        <button
          type="button"
          className="btn-secondary mt-3 text-xs"
          onClick={onRetry}
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
