import { analyticsApi } from "./domains/analytics";
import { authApi } from "./domains/auth";
import { engineApi } from "./domains/engine";
import { liveApi } from "./domains/live";
import { marketDataApi } from "./domains/marketData";
import { optimizationApi } from "./domains/optimization";
import { replayApi } from "./domains/replay";
import { validationApi } from "./domains/validation";

export {
  apiFetch,
  clearToken,
  downloadExport,
  getToken,
  setToken,
} from "./client";
export type * from "./types";

export const api = {
  ...authApi,
  ...engineApi,
  ...validationApi,
  ...optimizationApi,
  ...replayApi,
  ...liveApi,
  ...analyticsApi,
  ...marketDataApi,
};
