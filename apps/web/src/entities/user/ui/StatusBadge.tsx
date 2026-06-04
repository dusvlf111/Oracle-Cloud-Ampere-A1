import * as React from "react";

import { cn } from "@/shared";

export interface StatusBadgeProps {
  status: string;
  className?: string;
}

const STATUS_LABELS: Record<string, string> = {
  pending: "승인 대기",
  active: "활성",
  disabled: "비활성",
};

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  active: "bg-green-100 text-green-800",
  disabled: "bg-gray-100 text-gray-500",
};

/** Coloured pill for a user's account status (PRD §6.1). */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <span
      data-testid="user-status-badge"
      data-status={status}
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold",
        STATUS_STYLES[status] ?? "bg-gray-100 text-gray-600",
        className,
      )}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}
