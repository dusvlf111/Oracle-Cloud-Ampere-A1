"use client";

import { Menu } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { LogoutButton } from "@/features/auth-logout";

export interface HeaderProps {
  title?: string;
  /** Invoked by the mobile hamburger button to open the nav drawer. */
  onMenuClick?: () => void;
}

/** Top bar with the page title and a logout action (PRD §7.4, §7.7). */
export function Header({ title = "Dashboard", onMenuClick }: HeaderProps) {
  const router = useRouter();
  return (
    <header
      data-testid="header"
      className="flex items-center justify-between border-b border-gray-200 px-4 py-3"
    >
      <div className="flex items-center gap-2">
        {/* Hamburger: only visible below md (desktop uses the static rail). */}
        <button
          type="button"
          data-testid="menu-button"
          aria-label="Open navigation"
          onClick={onMenuClick}
          className="-ml-1 flex h-11 w-11 items-center justify-center rounded text-gray-600 hover:bg-gray-100 md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="text-lg font-semibold text-gray-800">{title}</h1>
      </div>
      <LogoutButton onSuccess={() => router.replace("/login")} />
    </header>
  );
}
