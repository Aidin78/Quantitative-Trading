export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const REQUEST_TIMEOUT_MS = 15_000;

/** A failed API call. `connectivity` means the request never reached the API
 * (backend down, wrong port, CORS, timeout) — distinct from an HTTP error. */
export class ApiError extends Error {
  status?: number;
  connectivity: boolean;

  constructor(
    message: string,
    opts: { status?: number; connectivity?: boolean } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = opts.status;
    this.connectivity = opts.connectivity ?? false;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function setToken(token: string) {
  localStorage.setItem("access_token", token);
}

export function clearToken() {
  localStorage.removeItem("access_token");
}

function authHeaders(extra?: HeadersInit): Record<string, string> {
  const headers: Record<string, string> = {
    ...(extra as Record<string, string> | undefined),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
    });
  } catch {
    throw new ApiError(
      `Can't reach the API at ${API_BASE}. Is the backend running? ` +
        `(cd backend && poetry run uvicorn src.main:app --port 8000)`,
      { connectivity: true },
    );
  } finally {
    clearTimeout(timer);
  }
}

export async function downloadExport(
  path: string,
  filename: string,
): Promise<void> {
  const res = await request(path, { headers: authHeaders() });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(text || res.statusText, { status: res.status });
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await request(path, {
    ...init,
    headers: authHeaders({
      "Content-Type": "application/json",
      ...(init?.headers as Record<string, string> | undefined),
    }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(text || res.statusText, { status: res.status });
  }
  return res.json() as Promise<T>;
}
