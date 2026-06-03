"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { LogoutButton } from "@/features/auth-logout";

export interface HeaderProps {
  title?: string;
}

/** Top bar with the page title and a logout action (PRD §7.4, §7.7). */
export function Header({ title = "Dashboard" }: HeaderProps) {
  const router = useRouter();
  return (
    <header
      data-testid="header"
      className="flex items-center justify-between border-b border-gray-200 px-4 py-3"
    >
      <h1 className="text-lg font-semibold text-gray-800">{title}</h1>
      <LogoutButton onSuccess={() => router.replace("/login")} />
    </header>
  );
}
