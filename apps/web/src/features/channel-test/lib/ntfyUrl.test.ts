import { describe, expect, it } from "vitest";

import { joinNtfyUrl, NtfyUrlError, parseNtfyUrl } from "./ntfyUrl";

describe("parseNtfyUrl", () => {
  it("splits the public ntfy.sh URL into server_url + topic", () => {
    expect(parseNtfyUrl("https://ntfy.sh/my-topic")).toEqual({
      server_url: "https://ntfy.sh",
      topic: "my-topic",
    });
  });

  it("tolerates a trailing slash", () => {
    expect(parseNtfyUrl("https://ntfy.sh/my-topic/")).toEqual({
      server_url: "https://ntfy.sh",
      topic: "my-topic",
    });
  });

  it("keeps the base path on a self-hosted instance with a deep path", () => {
    expect(parseNtfyUrl("https://ntfy.example.com/base/oci-alerts")).toEqual({
      server_url: "https://ntfy.example.com/base",
      topic: "oci-alerts",
    });
  });

  it("handles a self-hosted root URL with a single topic", () => {
    expect(parseNtfyUrl("https://ntfy.supabin.com/claude")).toEqual({
      server_url: "https://ntfy.supabin.com",
      topic: "claude",
    });
  });

  it("trims surrounding whitespace", () => {
    expect(parseNtfyUrl("  https://ntfy.sh/spaced  ")).toEqual({
      server_url: "https://ntfy.sh",
      topic: "spaced",
    });
  });

  it("throws when the topic segment is missing (origin only)", () => {
    expect(() => parseNtfyUrl("https://ntfy.sh")).toThrow(NtfyUrlError);
    expect(() => parseNtfyUrl("https://ntfy.sh/")).toThrow(
      /Missing topic/,
    );
  });

  it("throws on empty input", () => {
    expect(() => parseNtfyUrl("   ")).toThrow(/Missing topic/);
  });

  it("throws on a non-URL string", () => {
    expect(() => parseNtfyUrl("not a url")).toThrow(NtfyUrlError);
  });

  it("throws on a non-http(s) protocol", () => {
    expect(() => parseNtfyUrl("ftp://ntfy.sh/topic")).toThrow(
      /Invalid URL/,
    );
  });
});

describe("joinNtfyUrl", () => {
  it("joins server_url and topic", () => {
    expect(joinNtfyUrl("https://ntfy.sh", "my-topic")).toBe(
      "https://ntfy.sh/my-topic",
    );
  });

  it("tolerates a trailing slash on server_url", () => {
    expect(joinNtfyUrl("https://ntfy.sh/", "my-topic")).toBe(
      "https://ntfy.sh/my-topic",
    );
  });

  it("preserves a base path on self-hosted instances", () => {
    expect(joinNtfyUrl("https://ntfy.example.com/base", "topic")).toBe(
      "https://ntfy.example.com/base/topic",
    );
  });

  it("round-trips with parseNtfyUrl", () => {
    const url = "https://ntfy.example.com/base/oci-alerts";
    const { server_url, topic } = parseNtfyUrl(url);
    expect(joinNtfyUrl(server_url, topic)).toBe(url);
  });

  it("returns an empty string when both parts are empty", () => {
    expect(joinNtfyUrl("", "")).toBe("");
  });
});
