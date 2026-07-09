const STORAGE_KEY = "qt:activeOptimizationSweepId";

export function getActiveOptimizationSweepId(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(STORAGE_KEY);
}

export function setActiveOptimizationSweepId(id: string): void {
  sessionStorage.setItem(STORAGE_KEY, id);
}

export function clearActiveOptimizationSweepId(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}
