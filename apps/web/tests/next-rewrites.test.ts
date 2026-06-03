import { afterEach, describe, expect, it } from "vitest";

import config from "../next.config";

const ORIGINAL = process.env.INTERNAL_API_URL;

afterEach(() => {
  if (ORIGINAL === undefined) delete process.env.INTERNAL_API_URL;
  else process.env.INTERNAL_API_URL = ORIGINAL;
});

describe("next.config rewrites", () => {
  it("proxies /api/:path* to INTERNAL_API_URL", async () => {
    process.env.INTERNAL_API_URL = "http://server:8000";
    const rewrites = await config.rewrites!();
    const rules = Array.isArray(rewrites) ? rewrites : rewrites.afterFiles;
    expect(rules).toContainEqual({
      source: "/api/:path*",
      destination: "http://server:8000/api/:path*",
    });
  });

  it("falls back to http://server:8000 when INTERNAL_API_URL is unset", async () => {
    delete process.env.INTERNAL_API_URL;
    const rewrites = await config.rewrites!();
    const rules = Array.isArray(rewrites) ? rewrites : rewrites.afterFiles;
    expect(rules[0].destination).toBe("http://server:8000/api/:path*");
  });

  it("respects a custom internal URL", async () => {
    process.env.INTERNAL_API_URL = "http://api.internal:9000";
    const rewrites = await config.rewrites!();
    const rules = Array.isArray(rewrites) ? rewrites : rewrites.afterFiles;
    expect(rules[0].destination).toBe("http://api.internal:9000/api/:path*");
  });
});
