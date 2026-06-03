import { apiFetch } from "@/shared";

/** POST /api/auth/logout — clears the server session (204). */
export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}
