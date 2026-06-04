import { describe, expect, it } from "vitest";

import { formatRelativeTime } from "./time";

const NOW = Date.parse("2026-06-04T12:00:00Z");

describe("formatRelativeTime", () => {
  it("returns — for null/undefined", () => {
    expect(formatRelativeTime(null, NOW)).toBe("—");
    expect(formatRelativeTime(undefined, NOW)).toBe("—");
  });

  it("returns 방금 전 for very recent or future times", () => {
    expect(formatRelativeTime("2026-06-04T11:59:55Z", NOW)).toBe("방금 전");
    expect(formatRelativeTime("2026-06-04T12:00:30Z", NOW)).toBe("방금 전");
  });

  it("formats seconds, minutes, hours and days", () => {
    expect(formatRelativeTime("2026-06-04T11:59:30Z", NOW)).toBe("30초 전");
    expect(formatRelativeTime("2026-06-04T11:55:00Z", NOW)).toBe("5분 전");
    expect(formatRelativeTime("2026-06-04T09:00:00Z", NOW)).toBe("3시간 전");
    expect(formatRelativeTime("2026-06-02T12:00:00Z", NOW)).toBe("2일 전");
  });

  it("falls back to the raw string when unparseable", () => {
    expect(formatRelativeTime("not-a-date", NOW)).toBe("not-a-date");
  });
});
