import type { AttemptRead } from "@/shared/api/schemas/attemptRead";

/**
 * Attempt as returned by the API (PRD §6, §7.4).
 *
 * The read model now carries the resolved ``config_name`` / ``credential_name``
 * (null when the config/credential was deleted) so the UI can show
 * human-readable names instead of bare ids.
 */
export type Attempt = AttemptRead;

/** Domain attempt statuses (PRD §6, §7.3.1; hardening §2). */
export type AttemptStatus =
  | "success"
  | "out_of_capacity"
  | "rate_limited"
  | "auth_error"
  | "config_error"
  | "other_error";
