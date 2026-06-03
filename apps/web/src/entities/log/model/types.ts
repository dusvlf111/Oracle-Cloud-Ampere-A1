/** Log domain types — mirror the server `LogEntry` / `LogPage` (PRD §8). */

export const LOG_LEVELS = [
  "DEBUG",
  "INFO",
  "WARNING",
  "ERROR",
  "CRITICAL",
] as const;

export type LogLevel = (typeof LOG_LEVELS)[number];

export interface LogEntry {
  id: number;
  timestamp: string; // ISO 8601 (UTC)
  level: LogLevel | string;
  logger: string;
  message: string;
  config_id: number | null;
  attempt_id: number | null;
  credential_id: number | null;
  extra: string | null; // JSON string
  exc_info: string | null; // traceback
}

export interface LogPage {
  items: LogEntry[];
  next_cursor: string | null;
  has_more: boolean;
}
