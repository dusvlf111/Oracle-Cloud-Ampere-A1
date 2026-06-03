import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "./mocks/server";

describe("MSW test infrastructure", () => {
  it("serves a registered handler", async () => {
    const res = await fetch("http://localhost:3000/api/healthz");
    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toEqual({ status: "ok" });
  });

  it("supports per-test handler overrides", async () => {
    server.use(
      http.get("http://localhost:3000/api/ping", () =>
        HttpResponse.json({ pong: true }),
      ),
    );
    const res = await fetch("http://localhost:3000/api/ping");
    await expect(res.json()).resolves.toEqual({ pong: true });
  });

  it("rejects unhandled requests (onUnhandledRequest: error)", async () => {
    await expect(
      fetch("http://localhost:3000/api/does-not-exist"),
    ).rejects.toThrow();
  });
});
