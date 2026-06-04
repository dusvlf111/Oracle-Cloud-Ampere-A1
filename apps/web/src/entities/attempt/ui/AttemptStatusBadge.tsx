import * as React from "react";

import { cn } from "@/shared";

const STATUS_STYLES: Record<string, { label: string; className: string }> = {
  success: { label: "success", className: "bg-green-100 text-green-800" },
  out_of_capacity: {
    label: "out of capacity",
    className: "bg-amber-100 text-amber-800",
  },
  rate_limited: { label: "rate limited", className: "bg-orange-100 text-orange-800" },
  auth_error: { label: "auth error", className: "bg-red-100 text-red-800" },
  config_error: { label: "config error", className: "bg-rose-100 text-rose-800" },
  other_error: { label: "error", className: "bg-gray-200 text-gray-700" },
};

export interface AttemptStatusBadgeProps {
  status: string;
}

/** Colored badge for an Attempt status (PRD §7.4). */
export function AttemptStatusBadge({ status }: AttemptStatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? {
    label: status,
    className: "bg-gray-200 text-gray-700",
  };
  return (
    <span
      data-testid="attempt-status-badge"
      data-status={status}
      className={cn(
        "inline-block rounded px-1.5 py-0.5 text-xs font-semibold",
        style.className,
      )}
    >
      {style.label}
    </span>
  );
}
