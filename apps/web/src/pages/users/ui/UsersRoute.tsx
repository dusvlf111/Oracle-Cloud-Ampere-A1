"use client";

import * as React from "react";

import { useSession } from "@/entities/user";

import { UsersPage } from "./UsersPage";

/** Friendly notice shown when a non-admin reaches `/users` (PRD §6.1). */
function AccessDenied() {
  return (
    <main className="mx-auto flex max-w-md flex-col items-center gap-3 p-8 text-center">
      <h1 className="text-lg font-semibold">접근 권한이 없습니다</h1>
      <p data-testid="users-access-denied" className="text-sm text-gray-600">
        유저 관리는 관리자만 이용할 수 있습니다.
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
        <p className="text-sm text-gray-500">불러오는 중…</p>
      </main>
    );
  }

  if (!isAdmin) {
    return <AccessDenied />;
  }

  return <UsersPage />;
}
