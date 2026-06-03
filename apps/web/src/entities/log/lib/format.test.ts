import { describe, expect, it } from "vitest";

import { formatLocalTimestamp, formatShortTimestamp } from "./format";

describe("formatShortTimestamp", () => {
  it("renders time only (HH:MM:SS) for a valid ISO string", () => {
    const out = formatShortTimestamp("2026-06-03T10:30:11.000Z");
    // Time-only: three colon-separated 2-digit groups, no date separators.
    expect(out).toMatch(/^\d{2}:\d{2}:\d{2}$/);
  });

  it("falls back to the raw input for an unparseable timestamp", () => {
    expect(formatShortTimestamp("not-a-date")).toBe("not-a-date");
  });

  it("differs from the full local timestamp (which includes the date)", () => {
    const iso = "2026-06-03T10:30:11.000Z";
    expect(formatShortTimestamp(iso).length).toBeLessThan(
      formatLocalTimestamp(iso).length,
    );
  });
});
