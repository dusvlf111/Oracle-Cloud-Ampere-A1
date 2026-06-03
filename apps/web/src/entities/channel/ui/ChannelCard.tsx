"use client";

import { Bell, Hash, MessageCircle, Send, Webhook } from "lucide-react";
import * as React from "react";

import { cn } from "@/shared";

import type { Channel } from "../model/types";

export interface ChannelCardProps {
  channel: Channel;
  /** Optional action slot (e.g. test-send / edit / delete). */
  actions?: React.ReactNode;
}

/** Icon per channel type; falls back to a generic bell for unknown types. */
function TypeIcon({ type }: { type: string }) {
  const cls = "size-4 text-gray-500";
  switch (type) {
    case "discord":
      return <MessageCircle data-testid="channel-icon-discord" className={cls} aria-hidden />;
    case "slack":
      return <Hash data-testid="channel-icon-slack" className={cls} aria-hidden />;
    case "telegram":
      return <Send data-testid="channel-icon-telegram" className={cls} aria-hidden />;
    case "ntfy":
      return <Webhook data-testid="channel-icon-ntfy" className={cls} aria-hidden />;
    default:
      return <Bell data-testid="channel-icon-unknown" className={cls} aria-hidden />;
  }
}

/** Render the (already server-masked) config object as key/value rows. */
function configRows(config: Channel["config"]): Array<[string, string]> {
  return Object.entries(config).map(([k, v]) => [
    k,
    Array.isArray(v) ? v.join(", ") : String(v),
  ]);
}

export function ChannelCard({ channel, actions }: ChannelCardProps) {
  const rows = configRows(channel.config);
  return (
    <div
      data-testid="channel-card"
      className="flex flex-col gap-2 rounded-md border border-gray-200 p-3"
    >
      <div className="flex items-center gap-2">
        <TypeIcon type={channel.type} />
        <span className="font-semibold">{channel.name}</span>
        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs uppercase text-gray-600">
          {channel.type}
        </span>
        <span
          data-testid="channel-enabled-badge"
          className={cn(
            "ml-auto rounded px-1.5 py-0.5 text-xs font-semibold",
            channel.enabled
              ? "bg-green-100 text-green-800"
              : "bg-gray-100 text-gray-500",
          )}
        >
          {channel.enabled ? "enabled" : "disabled"}
        </span>
      </div>
      <div className="flex flex-col gap-1">
        {rows.map(([key, value]) => (
          <div key={key} className="flex justify-between gap-3 text-xs">
            <span className="text-gray-500">{key}</span>
            <span className="truncate font-mono text-gray-800" title={value}>
              {value}
            </span>
          </div>
        ))}
      </div>
      {actions && <div className="flex justify-end gap-2">{actions}</div>}
    </div>
  );
}
