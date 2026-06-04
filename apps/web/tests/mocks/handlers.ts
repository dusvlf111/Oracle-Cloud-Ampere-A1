import { http, HttpResponse } from "msw";

const API = "http://localhost:3000/api";

/**
 * Base MSW handlers for the domain APIs (PRD §8). Per-test/per-feature suites
 * override these with `server.use(...)`. They return empty collections so that
 * page mounts which fetch lists don't trip `onUnhandledRequest: 'error'`.
 *
 * Push 5 (5.1): credentials / configs / channels / attempts base + healthz.
 */
export const handlers = [
  http.get("/api/healthz", () => HttpResponse.json({ status: "ok" })),

  // Default: admin already exists → login form. Setup tests override this.
  http.get(`${API}/auth/setup`, () =>
    HttpResponse.json({ needs_setup: false }),
  ),

  http.get(`${API}/credentials`, () => HttpResponse.json([])),
  http.get(`${API}/configs`, () => HttpResponse.json([])),
  http.get(`${API}/channels`, () => HttpResponse.json([])),
  http.get(`${API}/attempts`, () => HttpResponse.json([])),

  // OCI meta lookups (PRD §8). Default empty so config-create mounts without
  // tripping `onUnhandledRequest: 'error'`; per-test suites override these.
  http.get(`${API}/meta/availability-domains`, () => HttpResponse.json([])),
  http.get(`${API}/meta/images`, () => HttpResponse.json([])),
  http.get(`${API}/meta/subnets`, () => HttpResponse.json([])),

  // Dashboard polling-status widget (PRD §7.3). Default empty so the dashboard
  // mounts cleanly; per-test suites override with seeded rows.
  http.get(`${API}/status/polling`, () => HttpResponse.json([])),
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
