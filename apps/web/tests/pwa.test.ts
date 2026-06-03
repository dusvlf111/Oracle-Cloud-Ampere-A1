import { describe, expect, it } from "vitest";

import manifest from "../app/manifest";
import config from "../next.config";

describe("PWA manifest", () => {
  const m = manifest();

  it("declares the required standalone install fields", () => {
    expect(m.name).toBeTruthy();
    expect(m.short_name).toBeTruthy();
    expect(m.start_url).toBe("/");
    expect(m.display).toBe("standalone");
    expect(m.theme_color).toMatch(/^#[0-9a-f]{6}$/i);
    expect(m.background_color).toMatch(/^#[0-9a-f]{6}$/i);
  });

  it("ships 192/512 icons including a maskable variant", () => {
    const icons = m.icons ?? [];
    const sizes = icons.map((i) => i.sizes);
    expect(sizes).toContain("192x192");
    expect(sizes).toContain("512x512");

    const maskable = icons.filter((i) => i.purpose === "maskable");
    expect(maskable.map((i) => i.sizes).sort()).toEqual(["192x192", "512x512"]);

    // Every icon must be a PNG under /icons/.
    for (const icon of icons) {
      expect(icon.type).toBe("image/png");
      expect(icon.src).toMatch(/^\/icons\/.+\.png$/);
    }
  });
});

describe("next.config Serwist integration", () => {
  it("preserves the /api proxy rewrite after the Serwist wrapper", async () => {
    const rewrites = await config.rewrites!();
    const rules = Array.isArray(rewrites) ? rewrites : rewrites.afterFiles;
    expect(rules![0].source).toBe("/api/:path*");
  });

  it("keeps standalone output and FSD-safe page extensions", () => {
    expect(config.output).toBe("standalone");
    expect(config.pageExtensions).toEqual(["tsx", "jsx"]);
  });
});
