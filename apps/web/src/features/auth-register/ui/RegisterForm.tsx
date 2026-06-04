"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as React from "react";
import { useForm } from "react-hook-form";

import { Button, Input, Label, isApiError } from "@/shared";

import { register as registerUser, type RegisterResult } from "../model/register";
import { registerSchema, type RegisterValues } from "../model/schema";

export interface RegisterFormProps {
  /**
   * First-ever signup (`needs_setup`) renders the "관리자 계정 생성" copy and
   * expects an auto-login; subsequent signups render "가입 신청".
   */
  mode: "setup" | "signup";
  /** Called when the result is an active session (admin bootstrap auto-login). */
  onAutoLogin?: (result: RegisterResult) => void;
  /** Called when the account was created but is pending approval. */
  onPending?: (result: RegisterResult) => void;
}

function messageForError(err: unknown): string {
  if (isApiError(err)) {
    if (err.code === "rate_limited") {
      const retry = err.details?.["retry_after_sec"];
      return typeof retry === "number"
        ? `시도가 너무 많습니다. ${retry}초 후 다시 시도하세요.`
        : "시도가 너무 많습니다. 잠시 후 다시 시도하세요.";
    }
    if (err.code === "username_taken") {
      return "이미 사용 중인 사용자명입니다.";
    }
    return err.message;
  }
  return "문제가 발생했습니다. 다시 시도해 주세요.";
}

export function RegisterForm({ mode, onAutoLogin, onPending }: RegisterFormProps) {
  const [formError, setFormError] = React.useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { username: "", password: "", confirm: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const result = await registerUser({
        username: values.username,
        password: values.password,
      });
      // The API decides the resulting state: first user → active (auto-login),
      // everyone after → pending (no session).
      if (result.status === "active") {
        onAutoLogin?.(result);
      } else {
        onPending?.(result);
      }
    } catch (err) {
      setFormError(messageForError(err));
    }
  });

  const submitLabel = mode === "setup" ? "관리자 계정 생성" : "가입 신청";
  const submittingLabel = mode === "setup" ? "계정 생성 중..." : "신청 중...";

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1">
        <Label htmlFor="username">사용자명</Label>
        <Input
          id="username"
          autoComplete="username"
          className="min-h-11 text-base"
          {...register("username")}
        />
        {errors.username && (
          <p role="alert" className="text-sm text-red-600">
            {errors.username.message}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="password">비밀번호</Label>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          className="min-h-11 text-base"
          {...register("password")}
        />
        {errors.password && (
          <p role="alert" className="text-sm text-red-600">
            {errors.password.message}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <Label htmlFor="confirm">비밀번호 확인</Label>
        <Input
          id="confirm"
          type="password"
          autoComplete="new-password"
          className="min-h-11 text-base"
          {...register("confirm")}
        />
        {errors.confirm && (
          <p role="alert" className="text-sm text-red-600">
            {errors.confirm.message}
          </p>
        )}
      </div>

      {formError && (
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}

      <Button type="submit" className="min-h-11" disabled={isSubmitting}>
        {isSubmitting ? submittingLabel : submitLabel}
      </Button>
    </form>
  );
}
