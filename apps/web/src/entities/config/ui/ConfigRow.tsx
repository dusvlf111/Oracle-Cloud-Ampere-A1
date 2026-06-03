"use client";

import * as React from "react";

import { cn } from "@/shared";

import type { Config } from "../model/types";

export interface ConfigRowProps {
  config: Config;
  /** Optional action slot (e.g. toggle / edit / delete). */
  actions?: React.ReactNode;
}

/** Single InstanceConfig row with an enabled/disabled badge (PRD §7.2). */
export function ConfigRow({ config, actions }: ConfigRowProps) {
  const c = config;
  return (
    <div
      data-testid="config-row"
      className="flex items-center gap-3 border-b border-gray-100 px-3 py-2 text-sm"
    >
      <span
        data-testid="config-enabled-badge"
        className={cn(
          "shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold",
          c.enabled
            ? "bg-green-100 text-green-800"
            : "bg-gray-100 text-gray-500",
        )}
      >
        {c.enabled ? "enabled" : "disabled"}
      </span>
      <span className="font-medium">{c.name}</span>
      <span className="text-gray-500">
        {c.shape} · {c.ocpus} OCPU · {c.memory_gb} GB · {c.boot_volume_gb} GB boot
      </span>
      <span className="text-xs text-gray-400">
        every {c.retry_interval_sec}s
        {c.max_attempts != null ? ` · max ${c.max_attempts}` : ""}
      </span>
      {c.channel_ids.length > 0 && (
        <span className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-700">
          {c.channel_ids.length} channel
          {c.channel_ids.length === 1 ? "" : "s"}
        </span>
      )}
      {actions && <div className="ml-auto flex gap-2">{actions}</div>}
    </div>
  );
}
