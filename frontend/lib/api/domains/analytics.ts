import { apiFetch, downloadExport } from "../client";
import type { AnalyticsHeatmap, AnalyticsOverview } from "../types";

export const analyticsApi = {
  analyticsOverview: (period = "30d") =>
    apiFetch<AnalyticsOverview>(`/api/v1/analytics/overview?period=${period}`),
  analyticsHeatmap: (period = "30d") =>
    apiFetch<AnalyticsHeatmap>(`/api/v1/analytics/heatmap?period=${period}`),
  exportDecisions: () =>
    downloadExport("/api/v1/decisions/export?format=csv", "decisions.csv"),
};
