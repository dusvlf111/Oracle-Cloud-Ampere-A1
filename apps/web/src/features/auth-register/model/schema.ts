import { z } from "zod";

/** Registration form schema (PRD §6.1). Mirrors API `RegisterRequest`. */
export const registerSchema = z
  .object({
    username: z.string().min(3, "Username must be at least 3 characters"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm: z.string().min(1, "Please confirm your password"),
  })
  .refine((v) => v.password === v.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });

export type RegisterValues = z.infer<typeof registerSchema>;
