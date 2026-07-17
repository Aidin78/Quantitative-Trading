import { apiFetch } from "../client";
import type { HealthStatus } from "../types";

export const authApi = {
  health: () => apiFetch<HealthStatus>("/health"),
  login: (username: string, password: string) =>
    apiFetch<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
};
