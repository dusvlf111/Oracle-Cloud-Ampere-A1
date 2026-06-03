import { apiFetch } from "@/shared";

import type { LoginValues } from "./schema";

export interface LoginResult {
  username: string;
}

/** POST /api/auth/login — throws ApiError on 401/429/etc. */
export function login(values: LoginValues): Promise<LoginResult> {
  return apiFetch<LoginResult>("/auth/login", {
    method: "POST",
    json: values,
  });
}
