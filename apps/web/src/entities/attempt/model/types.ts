import type { Attempt } from "@/shared/api/schemas/attempt";

/** Attempt as returned by the API (PRD §6, §7.4). */
export type { Attempt };

/** Domain attempt statuses (PRD §6, §7.3.1). */
export type AttemptStatus =
  | "success"
  | "out_of_capacity"
  | "rate_limited"
  | "auth_error"
  | "other_error";
