import { LOG_LEVELS, type LogLevel } from "@/entities/log";

export interface LogFilter {
  levels: LogLevel[];
  logger: string;
  configId: string;
  since: string;
  until: string;
  q: string;
}

export const EMPTY_FILTER: LogFilter = {
  levels: [],
  logger: "",
  configId: "",
  since: "",
  until: "",
  q: "",
};

export { LOG_LEVELS };
export type { LogLevel };

/** Build a `URLSearchParams` query string for `/api/logs[/stream]` (PRD §8). */
export function filterToQuery(filter: LogFilter): string {
  const params = new URLSearchParams();
  for (const level of filter.levels) params.append("levels", level);
  if (filter.logger.trim()) params.set("logger", filter.logger.trim());
  if (filter.configId.trim()) params.set("config_id", filter.configId.trim());
  if (filter.since) params.set("since", new Date(filter.since).toISOString());
  if (filter.until) params.set("until", new Date(filter.until).toISOString());
  if (filter.q.trim()) params.set("q", filter.q.trim());
  return params.toString();
}
