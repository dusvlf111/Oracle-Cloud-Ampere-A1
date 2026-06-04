import { z } from "zod";

/** Registration form schema (PRD §6.1). Mirrors API `RegisterRequest`. */
export const registerSchema = z
  .object({
    username: z.string().min(3, "사용자명은 3자 이상이어야 합니다"),
    password: z.string().min(8, "비밀번호는 8자 이상이어야 합니다"),
    confirm: z.string().min(1, "비밀번호 확인을 입력하세요"),
  })
  .refine((v) => v.password === v.confirm, {
    path: ["confirm"],
    message: "비밀번호가 일치하지 않습니다",
  });

export type RegisterValues = z.infer<typeof registerSchema>;
