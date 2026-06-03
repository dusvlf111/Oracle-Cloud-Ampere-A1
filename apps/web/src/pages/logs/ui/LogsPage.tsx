"use client";

import * as React from "react";

import { LogFilterBar, filterToQuery, type LogFilter } from "@/features/log-filter";
import { Button, isApiError } from "@/shared";
import { LogStream, useLogStream } from "@/widgets/log-stream";

import { deleteLogsBefore, fetchLogs } from "../model/api";

export interface LogsPageProps {
  /** Test seam — defaults to the live `useLogStream` hook. */
  useStream?: typeof useLogStream;
}

export function LogsPage({ useStream = useLogStream }: LogsPageProps) {
  const [query, setQuery] = React.useState("");
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);

  const stream = useStream({ query });

  const loadHistory = React.useCallback(
    async (q: string) => {
      setLoadError(null);
      try {
        const page = await fetchLogs(q);
        stream.clear();
        stream.prepend(page.items);
      } catch (err) {
        setLoadError(isApiError(err) ? err.message : "Failed to load logs.");
      }
    },
    [stream],
  );

  // Initial load (once on mount).
  const didLoad = React.useRef(false);
  React.useEffect(() => {
    if (didLoad.current) return;
    didLoad.current = true;
    void loadHistory("");
  }, [loadHistory]);

  const onFilterChange = (filter: LogFilter) => {
    const q = filterToQuery(filter);
    setQuery(q);
    void loadHistory(q);
  };

  const onConfirmDelete = async () => {
    setDeleting(true);
    try {
      await deleteLogsBefore(new Date().toISOString());
      setConfirmingDelete(false);
      stream.clear();
      await loadHistory(query);
    } catch (err) {
      setLoadError(isApiError(err) ? err.message : "Failed to delete logs.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <main className="flex h-screen flex-col">
      <div className="flex items-center justify-between px-3 py-2">
        <h1 className="text-lg font-semibold">Logs</h1>
        <Button type="button" onClick={() => setConfirmingDelete(true)}>
          Delete logs…
        </Button>
      </div>

      <LogFilterBar onChange={onFilterChange} />

      {loadError && (
        <p role="alert" className="px-3 py-2 text-sm text-red-600">
          {loadError}
        </p>
      )}

      <div className="min-h-0 flex-1">
        <LogStream
          rows={stream.rows}
          paused={stream.paused}
          connected={stream.connected}
          onTogglePause={() => stream.setPaused(!stream.paused)}
        />
      </div>

      {confirmingDelete && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Confirm delete logs"
          className="fixed inset-0 flex items-center justify-center bg-black/40"
        >
          <div className="w-80 rounded-md bg-white p-4 shadow-lg">
            <p className="text-sm">Delete all log records up to now?</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                disabled={deleting}
              >
                Cancel
              </Button>
              <Button type="button" onClick={onConfirmDelete} disabled={deleting}>
                {deleting ? "Deleting…" : "Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
