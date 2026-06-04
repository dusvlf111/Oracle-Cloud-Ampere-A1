"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as React from "react";
import { useForm } from "react-hook-form";

import { Button, Input, Label, isApiError } from "@/shared";

import { register as registerUser, type RegisterResult } from "../model/register";
import { registerSchema, type RegisterValues } from "../model/schema";

export interface RegisterFormProps {
  /**
   * First-ever signup (`needs_setup`) renders the "Create admin account" copy
   * and expects an auto-login; subsequent signups render "Sign up".
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
        ? `Too many attempts. Try again in ${retry}s.`
        : "Too many attempts. Please try again later.";
    }
    if (err.code === "username_taken") {
      return "That username is already taken.";
    }
    return err.message;
  }
  return "Something went wrong. Please try again.";
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

  const submitLabel = mode === "setup" ? "Create admin account" : "Sign up";
  const submittingLabel = mode === "setup" ? "Creating account..." : "Submitting...";

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1">
        <Label htmlFor="username">Username</Label>
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
        <Label htmlFor="password">Password</Label>
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
        <Label htmlFor="confirm">Confirm password</Label>
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
