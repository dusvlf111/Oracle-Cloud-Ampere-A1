import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/healthz", () => HttpResponse.json({ status: "ok" })),
];

/** Standard error envelope helper for tests (PRD §8). */
export function errorEnvelope(
  code: string,
  message: string,
  details: Record<string, unknown> | null = null,
) {
  return {
    error: { code, message, details, request_id: "01TEST" },
  };
}
