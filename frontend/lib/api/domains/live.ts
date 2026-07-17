import { apiFetch } from "../client";
import type { LiveStartRequest, LiveStatus } from "../types";

export const liveApi = {
  liveStatus: () => apiFetch<LiveStatus>("/api/v1/live/status"),
  startLive: (body: LiveStartRequest) =>
    apiFetch<LiveStatus>("/api/v1/live/start", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  stopLive: () => apiFetch<LiveStatus>("/api/v1/live/stop", { method: "POST" }),
  setLiveMode: (mode: "paper" | "live") =>
    apiFetch<LiveStatus>("/api/v1/live/mode", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
};
