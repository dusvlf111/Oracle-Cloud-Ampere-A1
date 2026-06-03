import { ApiError, type ApiErrorEnvelope } from "./errors";

const API_BASE = "/api";

export interface RequestOptions extends Omit<RequestInit, "body"> {
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
  const { json, headers, ...rest } = options;
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
