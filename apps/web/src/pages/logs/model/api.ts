import type { LogPage } from "@/entities/log";
import { apiFetch } from "@/shared";

/** GET /api/logs — historical, filtered, cursor-paginated query (PRD §8). */
export function fetchLogs(query: string, cursor?: string): Promise<LogPage> {
  const params = new URLSearchParams(query);
  if (cursor) params.set("cursor", cursor);
  const qs = params.toString();
  return apiFetch<LogPage>(`/logs${qs ? `?${qs}` : ""}`);
}

/** DELETE /api/logs?before=<iso> — bulk delete older records (admin). */
export function deleteLogsBefore(beforeIso: string): Promise<void> {
  const params = new URLSearchParams({ before: beforeIso });
  return apiFetch<void>(`/logs?${params.toString()}`, { method: "DELETE" });
}
