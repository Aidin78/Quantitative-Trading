const STORAGE_KEY = "qt:activeValidationJobId";

export function getActiveValidationJobId(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(STORAGE_KEY);
}

export function setActiveValidationJobId(id: string): void {
  sessionStorage.setItem(STORAGE_KEY, id);
}

export function clearActiveValidationJobId(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}
