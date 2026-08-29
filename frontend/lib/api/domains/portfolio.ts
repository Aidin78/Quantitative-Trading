import { apiFetch } from "../client";
import type { Portfolio } from "../types";

export const portfolioApi = {
  portfolio: () => apiFetch<Portfolio>("/api/v1/portfolio"),
};
