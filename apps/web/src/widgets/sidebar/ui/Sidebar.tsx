"use client";

import {
  Gauge,
  KeyRound,
  ListChecks,
  Bell,
  ScrollText,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { cn } from "@/shared";

export interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", icon: Gauge },
  { href: "/credentials", label: "Credentials", icon: KeyRound },
  { href: "/configs", label: "Configs", icon: ListChecks },
  { href: "/channels", label: "Channels", icon: Bell },
  { href: "/logs", label: "Logs", icon: ScrollText },
];

/** Left navigation for the authenticated app (PRD §5, §7.4). */
export function Sidebar() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Primary"
      data-testid="sidebar"
      className="flex w-52 shrink-0 flex-col gap-1 border-r border-gray-200 bg-gray-50 p-3"
    >
      <span className="px-2 pb-2 text-sm font-semibold text-gray-700">
        OCI Ampere A1
      </span>
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname?.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2 rounded px-2 py-1.5 text-sm",
              active
                ? "bg-blue-100 font-medium text-blue-800"
                : "text-gray-600 hover:bg-gray-100",
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
