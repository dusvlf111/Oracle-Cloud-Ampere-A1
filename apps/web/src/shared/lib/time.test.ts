import { describe, expect, it } from "vitest";

import { formatRelativeTime } from "./time";

const NOW = Date.parse("2026-06-04T12:00:00Z");

describe("formatRelativeTime", () => {
  it("returns — for null/undefined", () => {
    expect(formatRelativeTime(null, NOW)).toBe("—");
    expect(formatRelativeTime(undefined, NOW)).toBe("—");
  });

  it("returns just now for very recent or future times", () => {
    expect(formatRelativeTime("2026-06-04T11:59:55Z", NOW)).toBe("just now");
    expect(formatRelativeTime("2026-06-04T12:00:30Z", NOW)).toBe("just now");
  });

  it("formats seconds, minutes, hours and days", () => {
    expect(formatRelativeTime("2026-06-04T11:59:30Z", NOW)).toBe("30s ago");
    expect(formatRelativeTime("2026-06-04T11:55:00Z", NOW)).toBe("5m ago");
    expect(formatRelativeTime("2026-06-04T09:00:00Z", NOW)).toBe("3h ago");
    expect(formatRelativeTime("2026-06-02T12:00:00Z", NOW)).toBe("2d ago");
  });

  it("falls back to the raw string when unparseable", () => {
    expect(formatRelativeTime("not-a-date", NOW)).toBe("not-a-date");
  });
});
