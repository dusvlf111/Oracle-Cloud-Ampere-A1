import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/healthz", () => HttpResponse.json({ status: "ok" })),
];
