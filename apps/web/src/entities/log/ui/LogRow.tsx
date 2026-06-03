"use client";

import * as React from "react";

import { cn } from "@/shared";

import {
  formatLocalTimestamp,
  formatShortTimestamp,
  levelBadgeClass,
} from "../lib/format";
import type { LogEntry } from "../model/types";

export interface LogRowProps {
  entry: LogEntry;
}

function contextItems(entry: LogEntry): Array<[string, number]> {
  const out: Array<[string, number]> = [];
  if (entry.config_id != null) out.push(["config", entry.config_id]);
  if (entry.attempt_id != null) out.push(["attempt", entry.attempt_id]);
  if (entry.credential_id != null) out.push(["credential", entry.credential_id]);
  return out;
}

export function LogRow({ entry }: LogRowProps) {
  const [expanded, setExpanded] = React.useState(false);
  const ctx = contextItems(entry);
  const hasDetails = Boolean(entry.exc_info || entry.extra);

  return (
    <div className="border-b border-gray-100 px-3 py-2 font-mono text-xs">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-1 md:flex-nowrap">
        {/* Mobile: time only. Desktop: full local timestamp. */}
        <span className="shrink-0 text-gray-500 md:hidden">
          {formatShortTimestamp(entry.timestamp)}
        </span>
        <span className="hidden shrink-0 text-gray-500 md:inline">
          {formatLocalTimestamp(entry.timestamp)}
        </span>
        <span
          data-testid="log-level-badge"
          className={cn(
            "shrink-0 rounded px-1.5 py-0.5 font-semibold uppercase",
            levelBadgeClass(entry.level),
          )}
        >
          {entry.level}
        </span>
        <span className="shrink-0 text-gray-400">{entry.logger}</span>
        <span className="w-full break-words text-gray-900 md:w-auto md:flex-1">
          {entry.message}
        </span>
        {ctx.map(([label, value]) => (
          <span
            key={label}
            className="shrink-0 rounded bg-gray-50 px-1 text-gray-500"
          >
            {label}:{value}
          </span>
        ))}
        {hasDetails && (
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={expanded ? "Collapse details" : "Expand details"}
            onClick={() => setExpanded((v) => !v)}
            className="shrink-0 text-gray-400 hover:text-gray-700"
          >
            {expanded ? "▾" : "▸"}
          </button>
        )}
      </div>

      {expanded && entry.extra && (
        <pre className="mt-1 overflow-x-auto rounded bg-gray-50 p-2 text-gray-700">
          {entry.extra}
        </pre>
      )}
      {expanded && entry.exc_info && (
        <pre
          data-testid="log-traceback"
          className="mt-1 overflow-x-auto rounded bg-red-50 p-2 text-red-800"
        >
          {entry.exc_info}
        </pre>
      )}
    </div>
  );
}
