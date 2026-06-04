/**
 * ntfy URL helpers — split a single "ntfy URL" into the API's
 * `{ server_url, topic }` pair and join them back for the edit prefill.
 *
 * ntfy 알림은 결국 `<server>/<topic>` 으로의 POST 한 번이다 (PRD §7.5.2 / ntfy
 * docs). UX 를 위해 사용자에겐 URL 한 줄만 받고, 마지막 path segment 를 topic,
 * 나머지를 server_url 로 분해한다. self-host 와 깊은 base path 도 지원한다.
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
  "토픽이 없습니다 — 예: https://ntfy.sh/my-topic";
const INVALID_URL = "올바른 URL 이 아닙니다 — 예: https://ntfy.sh/my-topic";

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
