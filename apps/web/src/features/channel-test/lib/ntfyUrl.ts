/**
 * ntfy URL helpers — split a single "ntfy URL" into the API's
 * `{ server_url, topic }` pair and join them back for the edit prefill.
 *
 * An ntfy notification is ultimately a single POST to `<server>/<topic>` (PRD
 * §7.5.2 / ntfy docs). For UX we accept a single URL line from the user and
 * split it: the last path segment is the topic, the rest is the server_url.
 * Self-hosting and deep base paths are supported.
 *
 *   https://ntfy.sh/my-topic            → { server_url: "https://ntfy.sh", topic: "my-topic" }
 *   https://ntfy.example.com/base/topic → { server_url: "https://ntfy.example.com/base", topic: "topic" }
 */

export interface NtfyParts {
  server_url: string;
  topic: string;
}

export class NtfyUrlError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NtfyUrlError";
  }
}

const MISSING_TOPIC =
  "Missing topic — e.g. https://ntfy.sh/my-topic";
const INVALID_URL = "Invalid URL — e.g. https://ntfy.sh/my-topic";

/**
 * Parse a single ntfy URL into `{ server_url, topic }`.
 * The last non-empty path segment is the topic; everything before it (origin +
 * any base path) is the server_url. Trailing slashes are tolerated.
 * @throws {NtfyUrlError} when the URL is malformed or has no topic segment.
 */
export function parseNtfyUrl(input: string): NtfyParts {
  const raw = input.trim();
  if (!raw) throw new NtfyUrlError(MISSING_TOPIC);

  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new NtfyUrlError(INVALID_URL);
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new NtfyUrlError(INVALID_URL);
  }

  // Split the path, dropping empty segments (handles leading/trailing slashes).
  const segments = url.pathname.split("/").filter(Boolean);
  if (segments.length === 0) {
    throw new NtfyUrlError(MISSING_TOPIC);
  }

  const topic = decodeURIComponent(segments[segments.length - 1]);
  const basePath = segments.slice(0, -1).join("/");
  const server_url = basePath ? `${url.origin}/${basePath}` : url.origin;

  return { server_url, topic };
}

/**
 * Join a stored `{ server_url, topic }` back into one URL for the edit prefill.
 * Tolerates a trailing slash on server_url. Returns "" when both are empty.
 */
export function joinNtfyUrl(server_url: string, topic: string): string {
  const base = server_url.trim().replace(/\/+$/, "");
  const t = topic.trim();
  if (!base && !t) return "";
  if (!base) return t;
  if (!t) return base;
  return `${base}/${t}`;
}
