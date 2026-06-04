import { apiFetch } from "@/shared";

export interface RegisterInput {
  username: string;
  password: string;
}

/** API `RegisterResponse` — `{username, role, status}` (PRD §6.1). */
export interface RegisterResult {
  username: string;
  role: string;
  status: string;
}

/**
 * POST /api/auth/register — public signup (PRD §6.1).
 *
 * - First ever user → admin/active + auto-login (status `active`).
 * - Subsequent users → user/pending, no session (status `pending`).
 * - Duplicate username → 409 `username_taken`.
 *
 * Throws {@link ApiError} on 409/422/429.
 */
export function register(input: RegisterInput): Promise<RegisterResult> {
  return apiFetch<RegisterResult>("/auth/register", {
    method: "POST",
    json: { username: input.username, password: input.password },
  });
}

export interface SetupStatus {
  needs_setup: boolean;
}

/** GET /api/auth/setup — whether the first (admin) account still needs creating. */
export function getSetupStatus(): Promise<SetupStatus> {
  return apiFetch<SetupStatus>("/auth/setup");
}
