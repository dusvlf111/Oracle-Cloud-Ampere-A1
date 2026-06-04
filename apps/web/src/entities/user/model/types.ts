/** User domain types (PRD §6.1, §8). Mirrors the API `UserListItem`/`MeResponse`. */

/** Account lifecycle status. */
export type UserStatus = "pending" | "active" | "disabled";

/** Account role. */
export type UserRole = "admin" | "user";

/** A user row as returned by `GET /api/users` (admin only). */
export interface User {
  id: number;
  username: string;
  role: string;
  status: string;
  created_at: string;
  approved_at?: string | null;
}

/** The current session as returned by `GET /api/auth/me` (`{username, role, status}`). */
export interface Me {
  username: string;
  role: string;
  status: string;
}

/** Type guard: is the session an admin? */
export function isAdmin(me: Pick<Me, "role"> | null | undefined): boolean {
  return me?.role === "admin";
}
