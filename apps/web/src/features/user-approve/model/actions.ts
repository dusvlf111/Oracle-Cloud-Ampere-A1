"use client";

import { useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import {
  approveUser,
  disableUser,
  enableUser,
  rejectUser,
  usersQueryKey,
} from "@/entities/user";
import { isApiError } from "@/shared";

export type UserAction = "approve" | "reject" | "disable" | "enable";

const RUNNERS: Record<UserAction, (userId: number) => Promise<unknown>> = {
  approve: (id) => approveUser(id),
  reject: (id) => rejectUser(id),
  disable: (id) => disableUser(id),
  enable: (id) => enableUser(id),
};

export interface UseUserActionsResult {
  /** userId currently mutating (for per-row spinners), or null. */
  pendingId: number | null;
  error: string | null;
  run: (action: UserAction, userId: number) => Promise<boolean>;
  clearError: () => void;
}

/**
 * Mutations for the admin user-management actions (PRD §6.1). Each call hits the
 * generated POST endpoint and invalidates the user list so the table re-renders
 * with the new status. The last-admin guard surfaces as a friendly message.
 */
export function useUserActions(): UseUserActionsResult {
  const queryClient = useQueryClient();
  const [pendingId, setPendingId] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const run = React.useCallback(
    async (action: UserAction, userId: number) => {
      setError(null);
      setPendingId(userId);
      try {
        await RUNNERS[action](userId);
        await queryClient.invalidateQueries({ queryKey: usersQueryKey() });
        return true;
      } catch (err) {
        if (isApiError(err) && err.code === "last_admin") {
          setError("마지막 관리자는 비활성화할 수 없습니다.");
        } else {
          setError(isApiError(err) ? err.message : "작업에 실패했습니다.");
        }
        return false;
      } finally {
        setPendingId(null);
      }
    },
    [queryClient],
  );

  const clearError = React.useCallback(() => setError(null), []);

  return { pendingId, error, run, clearError };
}
