import * as React from "react";

import { cn } from "@/shared";

export interface RoleBadgeProps {
  role: string;
  className?: string;
}

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  user: "User",
};

const ROLE_STYLES: Record<string, string> = {
  admin: "bg-blue-100 text-blue-800",
  user: "bg-gray-100 text-gray-600",
};

/** Coloured pill for a user's role (PRD §6.1). */
export function RoleBadge({ role, className }: RoleBadgeProps) {
  return (
    <span
      data-testid="user-role-badge"
      data-role={role}
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold",
        ROLE_STYLES[role] ?? "bg-gray-100 text-gray-600",
        className,
      )}
    >
      {ROLE_LABELS[role] ?? role}
    </span>
  );
}
