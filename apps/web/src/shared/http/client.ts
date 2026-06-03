import { ApiError, type ApiErrorEnvelope } from "./errors";

const API_BASE = "/api";

export interface RequestOptions extends RequestInit {
  /** JSON-serialisable body; sets Content-Type automatically. */
  json?: unknown;
}

/**
 * Thin fetch wrapper used by features and as the future Orval mutator.
 *
 * - Always sends cookies (`credentials: 'include'`) for session auth.
 * - Parses the standard error envelope (PRD §8) and throws {@link ApiError}.
 * - Returns parsed JSON for 2xx, or `undefined` for 204/empty bodies.
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { json, headers, body, ...rest } = options;
  const init: RequestInit = {
    credentials: "include",
    ...rest,
    headers: {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  };
  if (json !== undefined) {
    init.body = JSON.stringify(json);
  } else if (body !== undefined) {
    // Raw body passthrough (e.g. FormData for multipart uploads). The browser
    // sets the correct Content-Type/boundary, so we must not force JSON above.
    init.body = body;
  }

  const url = path.startsWith("http")
    ? path
    : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

  const res = await fetch(url, init);

  if (!res.ok) {
    throw await toApiError(res);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

/**
 * Orval mutator (configured in `orval.config.ts` as `override.mutator`).
 *
 * Orval's generated React Query hooks call this with an axios-like config.
 * We translate it onto {@link apiFetch} so generated hooks share the same
 * cookie handling, base URL and standard error-envelope parsing.
 *
 * Notable behaviours:
 * - `params` are serialised to a query string (arrays repeat the key, matching
 *   FastAPI's `levels=A&levels=B` convention).
 * - `FormData` bodies are passed through untouched (no JSON Content-Type) so
 *   multipart uploads (credential private key) work.
 * - Plain-object bodies are sent as JSON.
 */
export interface HttpClientConfig {
  url: string;
  method: string;
  params?: Record<string, unknown>;
  data?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

function toQueryString(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const v of value) {
        if (v !== undefined && v !== null) search.append(key, String(v));
      }
    } else {
      search.append(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function httpClient<T>(config: HttpClientConfig): Promise<T> {
  const { url, method, params, data, headers, signal } = config;
  // Orval emits server-absolute paths (`/api/...`). `apiFetch` prepends its own
  // `/api` base, so strip the duplicate prefix to avoid `/api/api/...`.
  const normalised = url.startsWith(`${API_BASE}/`)
    ? url.slice(API_BASE.length)
    : url;
  const path = params ? `${normalised}${toQueryString(params)}` : normalised;

  const options: RequestOptions = {
    method: method.toUpperCase(),
    headers,
    signal,
  };

  if (data instanceof FormData) {
    // Let the browser set the multipart boundary; pass body through verbatim.
    // Orval emits `Content-Type: multipart/form-data` (no boundary) which would
    // corrupt the upload, so strip it and let fetch derive the correct value.
    if (options.headers) {
      const rest = { ...(options.headers as Record<string, string>) };
      delete rest["Content-Type"];
      delete rest["content-type"];
      options.headers = rest;
    }
    options.body = data;
  } else if (data !== undefined) {
    options.json = data;
  }

  return apiFetch<T>(path, options);
}

async function toApiError(res: Response): Promise<ApiError> {
  let envelope: Partial<ApiErrorEnvelope> | null = null;
  try {
    envelope = (await res.json()) as ApiErrorEnvelope;
  } catch {
    // non-JSON error body
  }
  const e = envelope?.error;
  return new ApiError(
    res.status,
    e?.code ?? "internal_error",
    e?.message ?? res.statusText ?? "Request failed",
    e?.details ?? null,
    e?.request_id ?? null,
  );
}
