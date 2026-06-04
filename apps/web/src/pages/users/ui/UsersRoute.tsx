"use client";

import * as React from "react";

import { useSession } from "@/entities/user";

import { UsersPage } from "./UsersPage";

/** Friendly notice shown when a non-admin reaches `/users` (PRD §6.1). */
function AccessDenied() {
  return (
    <main className="mx-auto flex max-w-md flex-col items-center gap-3 p-8 text-center">
      <h1 className="text-lg font-semibold">You don&apos;t have permission to view this page</h1>
      <p data-testid="users-access-denied" className="text-sm text-gray-600">
        User management is available to administrators only.
      </p>
    </main>
  );
}

/**
 * Route entry for `/users`. The server is the source of truth (it returns
 * 403/404 for non-admins on `GET /api/users`), but we also gate on the session
 * role client-side so a non-admin who navigates directly sees a clear notice
 * instead of a failed table fetch (PRD §6.1, §7).
 */
export function UsersRoute() {
  const { isLoading, isAdmin } = useSession();

  if (isLoading) {
    return (
      <main className="p-6">
        <p className="text-sm text-gray-500">Loading…</p>
      </main>
    );
  }

  if (!isAdmin) {
    return <AccessDenied />;
  }

  return <UsersPage />;
}
