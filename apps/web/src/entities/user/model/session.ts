"use client";

import { useMe } from "../api";
import { isAdmin, type Me } from "./types";

export interface SessionState {
  me: Me | null;
  isLoading: boolean;
  isError: boolean;
  /** Convenience flag derived from `me.role` (PRD §6.1). */
  isAdmin: boolean;
}

/**
 * Current session helper, layered on the generated `GET /api/auth/me` hook.
 *
 * Exposes the authenticated `{username, role, status}` plus an `isAdmin`
 * convenience flag so UI (sidebar, users page) can branch on role without
 * re-deriving it. A 401 (logged out) surfaces as `me: null` rather than an
 * error so callers can treat "no session" uniformly.
 */
export function useSession(): SessionState {
  const { data, isLoading, isError } = useMe<Me>({
    query: { retry: false, staleTime: 30_000 },
  });
  const me = data ?? null;
  return {
    me,
    isLoading,
    isError,
    isAdmin: isAdmin(me),
  };
}
