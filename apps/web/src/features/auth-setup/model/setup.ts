import { apiFetch } from "@/shared";

export interface SetupStatus {
  needs_setup: boolean;
}

export interface CreateAdminInput {
  username: string;
  password: string;
}

export interface CreateAdminResult {
  username: string;
}

/** GET /api/auth/setup — whether the admin account still needs to be created. */
export function getSetupStatus(): Promise<SetupStatus> {
  return apiFetch<SetupStatus>("/auth/setup");
}

/**
 * POST /api/auth/setup — create the admin (first signup) and auto-login.
 * Throws ApiError on 409 (already done) / 422 (validation) / 429.
 */
export function createAdmin(
  input: CreateAdminInput,
): Promise<CreateAdminResult> {
  return apiFetch<CreateAdminResult>("/auth/setup", {
    method: "POST",
    json: { username: input.username, password: input.password },
  });
}
