"use client";

import { keepPreviousData } from "@tanstack/react-query";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import * as React from "react";

import { useAttempts } from "../api";
import type { Attempt, AttemptStatus } from "../model/types";

import { AttemptCardList } from "./AttemptCardList";
import { AttemptStatusBadge } from "./AttemptStatusBadge";

const STATUS_OPTIONS: AttemptStatus[] = [
  "success",
  "out_of_capacity",
  "rate_limited",
  "auth_error",
  "other_error",
];

const REFETCH_INTERVAL_MS = 5000;
const DEFAULT_LIMIT = 50;

// Stable fallback — `data ?? []` inline would mint a NEW array every render,
// which makes useReactTable re-initialize each time and (while a filter
// change leaves `data` undefined) spirals into an infinite re-render loop
// that freezes the page. See TanStack Table "stable data reference" docs.
const NO_ROWS: Attempt[] = [];

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

/** "이름 (#id)" when the joined config name is present, else the bare id. */
function formatConfigLabel(name: string | null | undefined, id: number): string {
  return name ? `${name} (#${id})` : `#${id}`;
}

const columns: ColumnDef<Attempt>[] = [
  {
    header: "Time",
    accessorKey: "attempted_at",
    cell: ({ getValue }) => formatTime(getValue<string>()),
  },
  {
    header: "Config",
    id: "config",
    cell: ({ row }) => (
      <div className="flex flex-col">
        <span className="text-gray-800">
          {formatConfigLabel(row.original.config_name, row.original.config_id)}
        </span>
        {row.original.credential_name && (
          <span className="text-xs text-gray-500">
            {row.original.credential_name}
          </span>
        )}
      </div>
    ),
  },
  {
    header: "Status",
    accessorKey: "status",
    cell: ({ getValue }) => <AttemptStatusBadge status={getValue<string>()} />,
  },
  {
    header: "Duration",
    accessorKey: "duration_ms",
    cell: ({ getValue }) => formatDuration(getValue<number | null>()),
  },
  {
    header: "Detail",
    id: "detail",
    cell: ({ row }) =>
      row.original.instance_ocid ?? row.original.message ?? "—",
  },
];

export interface AttemptsTableProps {
  /** Optional fixed config filter (e.g. when embedded in a config detail). */
  defaultConfigId?: number;
}

/** Recent attempts table with config/status filters (PRD §7.4). */
export function AttemptsTable({ defaultConfigId }: AttemptsTableProps) {
  const [configId, setConfigId] = React.useState<string>(
    defaultConfigId != null ? String(defaultConfigId) : "",
  );
  const [status, setStatus] = React.useState<string>("");

  const params = {
    limit: DEFAULT_LIMIT,
    ...(configId !== "" ? { config_id: Number(configId) } : {}),
    ...(status !== "" ? { status } : {}),
  };

  const { data, isLoading } = useAttempts(params, {
    query: {
      refetchInterval: REFETCH_INTERVAL_MS,
      // Keep showing the previous rows while a filter change refetches —
      // avoids the table collapsing to empty (and re-rendering from scratch)
      // on every dropdown interaction.
      placeholderData: keepPreviousData,
    },
  });

  const rows = data ?? NO_ROWS;
  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div data-testid="attempts-table" className="flex flex-col gap-3">
      {/* Mobile: full-width stacked filters, 44px touch targets and 16px font
          (text-base) so iOS Safari does not auto-zoom on focus. Desktop keeps
          the compact inline look. */}
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <label className="flex w-full flex-col gap-1 text-xs text-gray-600 sm:w-auto">
          Config ID
          <input
            aria-label="Filter by config id"
            value={configId}
            onChange={(e) => setConfigId(e.target.value)}
            className="min-h-11 w-full rounded border border-gray-300 bg-white px-3 py-2 text-base sm:min-h-0 sm:w-auto sm:px-2 sm:py-1 sm:text-sm"
            inputMode="numeric"
          />
        </label>
        <label className="flex w-full flex-col gap-1 text-xs text-gray-600 sm:w-auto">
          Status
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="min-h-11 w-full appearance-none rounded border border-gray-300 bg-white px-3 py-2 text-base sm:min-h-0 sm:w-auto sm:appearance-auto sm:px-2 sm:py-1 sm:text-sm"
          >
            <option value="">All</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Desktop: full table. Hidden below md in favor of the card list. */}
      <table className="hidden w-full border-collapse text-left text-sm md:table">
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="border-b border-gray-200">
              {hg.headers.map((h) => (
                <th key={h.id} className="px-3 py-2 font-semibold text-gray-700">
                  {flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              data-testid="attempt-row"
              className="border-b border-gray-100"
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile: stacked cards from the same data. Hidden from md up. */}
      <div className="md:hidden">
        <AttemptCardList attempts={rows} />
      </div>

      {!isLoading && rows.length === 0 && (
        <p className="px-3 py-6 text-center text-sm text-gray-400">
          시도 이력이 없습니다.
        </p>
      )}
    </div>
  );
}
