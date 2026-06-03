"use client";

import * as React from "react";

import type { LogEntry } from "@/entities/log";

/** Injectable EventSource constructor (real one by default; mockable in tests). */
export type EventSourceCtor = new (url: string) => EventSource;

export interface UseLogStreamOptions {
  /** Query string from the active filter (PRD §8). */
  query?: string;
  /** Start paused (no subscription). */
  initialPaused?: boolean;
  /** Cap on retained rows before the oldest are dropped (PRD §7.6). */
  maxRows?: number;
  /** Override for tests. */
  eventSourceCtor?: EventSourceCtor;
}

export interface UseLogStreamResult {
  rows: LogEntry[];
  paused: boolean;
  connected: boolean;
  setPaused: (paused: boolean) => void;
  /** Seed historical rows (newest-first) before live tailing. */
  prepend: (history: LogEntry[]) => void;
  clear: () => void;
}

const DEFAULT_MAX_ROWS = 2000;
const STREAM_URL = "/api/logs/stream";

/**
 * Subscribe to the SSE log stream.
 *
 * - Opens an `EventSource` while not paused; closes it on pause/unmount so the
 *   server `log_bus` subscriber is released.
 * - Appends incoming `log` events, trimming to `maxRows`.
 * - Ignores `ping` heartbeats.
 */
export function useLogStream(
  options: UseLogStreamOptions = {},
): UseLogStreamResult {
  const {
    query = "",
    initialPaused = false,
    maxRows = DEFAULT_MAX_ROWS,
    eventSourceCtor,
  } = options;

  const [rows, setRows] = React.useState<LogEntry[]>([]);
  const [paused, setPaused] = React.useState(initialPaused);
  const [connected, setConnected] = React.useState(false);

  const Ctor: EventSourceCtor =
    eventSourceCtor ??
    (typeof EventSource !== "undefined"
      ? (EventSource as unknown as EventSourceCtor)
      : (undefined as unknown as EventSourceCtor));

  React.useEffect(() => {
    if (paused || !Ctor) {
      setConnected(false);
      return;
    }
    const url = query ? `${STREAM_URL}?${query}` : STREAM_URL;
    const es = new Ctor(url);
    setConnected(true);

    const onLog = (ev: MessageEvent) => {
      try {
        const entry = JSON.parse(ev.data) as LogEntry;
        setRows((prev) => {
          const next = [...prev, entry];
          return next.length > maxRows ? next.slice(next.length - maxRows) : next;
        });
      } catch {
        // malformed frame — ignore
      }
    };

    es.addEventListener("log", onLog as EventListener);
    return () => {
      es.removeEventListener("log", onLog as EventListener);
      es.close();
      setConnected(false);
    };
  }, [paused, query, maxRows, Ctor]);

  const prepend = React.useCallback((history: LogEntry[]) => {
    // History arrives newest-first; the stream list renders oldest→newest.
    setRows((prev) => [...[...history].reverse(), ...prev]);
  }, []);

  const clear = React.useCallback(() => setRows([]), []);

  return { rows, paused, connected, setPaused, prepend, clear };
}
