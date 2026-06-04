"use client";

import {
  Gauge,
  KeyRound,
  ListChecks,
  Bell,
  ScrollText,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { useSession } from "@/entities/user";
import { cn } from "@/shared";

export interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  /** When true, only rendered for an admin session (PRD §6.1). */
  adminOnly?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", icon: Gauge },
  { href: "/credentials", label: "Credentials", icon: KeyRound },
  { href: "/configs", label: "Configs", icon: ListChecks },
  { href: "/channels", label: "Channels", icon: Bell },
  { href: "/logs", label: "Logs", icon: ScrollText },
  { href: "/users", label: "유저 관리", icon: Users, adminOnly: true },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { isAdmin } = useSession();
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin);
  return (
    <>
      <span className="px-2 pb-2 text-sm font-semibold text-gray-700">
        OCI Ampere A1
      </span>
      {items.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname?.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              // 44px min touch target for mobile (PRD §7 a11y).
              "flex min-h-11 items-center gap-2 rounded px-2 py-1.5 text-sm",
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
    </>
  );
}

export interface SidebarProps {
  /** Controls the mobile drawer. When omitted, only the desktop rail renders. */
  open?: boolean;
  onClose?: () => void;
}

/**
 * Left navigation for the authenticated app (PRD §5, §7.4).
 *
 * Renders two presentations from a single slice (FSD-compliant — no
 * cross-slice imports): a static desktop rail (`md:` and up) and a mobile
 * slide-in drawer with overlay driven by `open`/`onClose`. The drawer closes
 * automatically when a route changes (via the link `onClick`).
 */
export function Sidebar({ open = false, onClose }: SidebarProps) {
  const pathname = usePathname();

  // Auto-close the drawer whenever the route changes (covers programmatic
  // navigation, not just link clicks). Intentionally keyed on `pathname` only;
  // `onClose` is a stable callback from the layout.
  const onCloseRef = React.useRef(onClose);
  onCloseRef.current = onClose;
  React.useEffect(() => {
    onCloseRef.current?.();
  }, [pathname]);

  return (
    <>
      {/* Desktop rail: hidden below md, always visible from md up. */}
      <nav
        aria-label="Primary"
        data-testid="sidebar"
        className="hidden w-52 shrink-0 flex-col gap-1 border-r border-gray-200 bg-gray-50 p-3 md:flex"
      >
        <NavLinks />
      </nav>

      {/* Mobile drawer: overlay + slide-in panel, hidden from md up. */}
      <div className="md:hidden">
        <div
          data-testid="sidebar-overlay"
          aria-hidden={!open}
          onClick={onClose}
          className={cn(
            "fixed inset-0 z-40 bg-black/40 transition-opacity",
            open ? "opacity-100" : "pointer-events-none opacity-0",
          )}
        />
        <nav
          aria-label="Primary"
          data-testid="sidebar-drawer"
          aria-hidden={!open}
          className={cn(
            "fixed inset-y-0 left-0 z-50 flex w-64 max-w-[80vw] flex-col gap-1 border-r border-gray-200 bg-gray-50 p-3 transition-transform duration-200",
            open ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <NavLinks onNavigate={onClose} />
        </nav>
      </div>
    </>
  );
}
