"use client";

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import * as React from "react";

import { useAttempts } from "../api";
import type { Attempt, AttemptStatus } from "../model/types";

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

const columns: ColumnDef<Attempt>[] = [
  {
    header: "Time",
    accessorKey: "attempted_at",
    cell: ({ getValue }) => formatTime(getValue<string>()),
  },
  { header: "Config", accessorKey: "config_id" },
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
    query: { refetchInterval: REFETCH_INTERVAL_MS },
  });

  const rows = data ?? [];
  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div data-testid="attempts-table" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col text-xs text-gray-600">
          Config ID
          <input
            aria-label="Filter by config id"
            value={configId}
            onChange={(e) => setConfigId(e.target.value)}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
            inputMode="numeric"
          />
        </label>
        <label className="flex flex-col text-xs text-gray-600">
          Status
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
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

      <table className="w-full border-collapse text-left text-sm">
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

      {!isLoading && rows.length === 0 && (
        <p className="px-3 py-6 text-center text-sm text-gray-400">
          시도 이력이 없습니다.
        </p>
      )}
    </div>
  );
}
