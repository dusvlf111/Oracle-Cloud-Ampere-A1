/** Standard error envelope from the API (PRD §8). */
export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown> | null;
    request_id: string;
  };
}

/** Typed error thrown by {@link apiFetch} for any non-2xx response. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown> | null;
  readonly requestId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> | null = null,
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}
