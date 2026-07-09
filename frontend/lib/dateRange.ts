export type DateRangePreset = "today" | "7d" | "30d" | "90d" | "180d";

export const DATE_RANGE_PRESETS: Array<{ id: DateRangePreset; label: string }> =
  [
    { id: "today", label: "Today" },
    { id: "7d", label: "7 days" },
    { id: "30d", label: "30 days" },
    { id: "90d", label: "90 days" },
    { id: "180d", label: "180 days" },
  ];

export function toDateInputValue(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

export function dateRangeForPreset(
  preset: DateRangePreset,
  reference: Date = new Date(),
): { start: string; end: string } {
  const end = toDateInputValue(reference);
  if (preset === "today") {
    return { start: end, end };
  }
  const days =
    preset === "7d" ? 7 : preset === "30d" ? 30 : preset === "180d" ? 180 : 90;
  return { start: toDateInputValue(addDays(reference, -days)), end };
}
