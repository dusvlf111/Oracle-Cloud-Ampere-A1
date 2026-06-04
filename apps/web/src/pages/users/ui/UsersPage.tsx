"use client";

import * as React from "react";

import {
  RoleBadge,
  StatusBadge,
  useUsers,
  type User,
} from "@/entities/user";
import { UserActions } from "@/features/user-approve";
import { formatRelativeTime } from "@/shared";

/** pending first, then by created_at ascending (oldest signups need action first). */
const STATUS_ORDER: Record<string, number> = {
  pending: 0,
  active: 1,
  disabled: 2,
};

function sortUsers(users: User[]): User[] {
  return [...users].sort((a, b) => {
    const byStatus =
      (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99);
    if (byStatus !== 0) return byStatus;
    return a.created_at.localeCompare(b.created_at);
  });
}

export function UsersPage() {
  const { data, isLoading, isError } = useUsers<User[]>();
  const users = React.useMemo(() => sortUsers(data ?? []), [data]);

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4">
      <h1 className="text-lg font-semibold">Users</h1>

      {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
      {isError && (
        <p role="alert" className="text-sm text-red-600">
          Failed to load the user list.
        </p>
      )}
      {!isLoading && !isError && users.length === 0 && (
        <p className="text-sm text-gray-500">No users.</p>
      )}

      {users.length > 0 && (
        <>
          {/* Desktop table */}
          <table
            data-testid="users-table"
            className="hidden w-full border-collapse text-left text-sm md:table"
          >
            <thead>
              <tr className="border-b border-gray-200 text-gray-500">
                <th className="py-2 pr-3 font-medium">Username</th>
                <th className="py-2 pr-3 font-medium">Role</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Joined</th>
                <th className="py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.id}
                  data-testid="user-row"
                  className="border-b border-gray-100"
                >
                  <td className="py-2 pr-3 font-medium">{u.username}</td>
                  <td className="py-2 pr-3">
                    <RoleBadge role={u.role} />
                  </td>
                  <td className="py-2 pr-3">
                    <StatusBadge status={u.status} />
                  </td>
                  <td className="py-2 pr-3 text-gray-500">
                    {formatRelativeTime(u.created_at)}
                  </td>
                  <td className="py-2">
                    <UserActions user={u} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Mobile cards */}
          <ul className="flex flex-col gap-3 md:hidden">
            {users.map((u) => (
              <li
                key={u.id}
                data-testid="user-card"
                className="flex flex-col gap-2 rounded-md border border-gray-200 p-3"
              >
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{u.username}</span>
                  <RoleBadge role={u.role} className="ml-auto" />
                  <StatusBadge status={u.status} />
                </div>
                <p className="text-xs text-gray-500">
                  Joined {formatRelativeTime(u.created_at)}
                </p>
                <UserActions user={u} />
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
