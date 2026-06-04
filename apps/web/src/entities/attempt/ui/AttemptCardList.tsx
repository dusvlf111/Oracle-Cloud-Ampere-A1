"use client";

import * as React from "react";

import type { Attempt } from "../model/types";

import { AttemptStatusBadge } from "./AttemptStatusBadge";

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatTime(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export interface AttemptCardListProps {
  attempts: Attempt[];
}

/**
 * Mobile card presentation of the attempts list (Push 7).
 *
 * Lives in the same `attempt` slice as `AttemptsTable` (FSD-compliant) and
 * renders the identical data/status semantics in a stacked, narrow-screen
 * layout. The desktop table and this list are toggled by responsive utility
 * classes in `AttemptsTable`.
 */
export function AttemptCardList({ attempts }: AttemptCardListProps) {
  return (
    <ul data-testid="attempt-card-list" className="flex flex-col gap-2">
      {attempts.map((a) => (
        <li
          key={a.id}
          data-testid="attempt-card"
          className="flex flex-col gap-1.5 rounded border border-gray-200 p-3 text-sm"
        >
          <div className="flex items-center justify-between gap-2">
            <AttemptStatusBadge status={a.status} />
            <span className="text-xs text-gray-500">{formatTime(a.attempted_at)}</span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
            <span className="flex flex-col">
              <span>
                <span className="text-gray-400">Config </span>
                {a.config_name ? `${a.config_name} (#${a.config_id})` : `#${a.config_id}`}
              </span>
              {a.credential_name && (
                <span className="text-gray-400">Account {a.credential_name}</span>
              )}
            </span>
            <span>
              <span className="text-gray-400">Duration </span>
              {formatDuration(a.duration_ms)}
            </span>
          </div>
          {(a.instance_ocid || a.message) && (
            <p className="break-all text-xs text-gray-700">
              {a.instance_ocid ?? a.message}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
