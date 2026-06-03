"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as React from "react";
import { useForm } from "react-hook-form";

import { Button, Input, Label, isApiError } from "@/shared";

import { login } from "../model/login";
import { loginSchema, type LoginValues } from "../model/schema";

export interface LoginFormProps {
  /** Called after a successful login (e.g. router.push('/')). */
  onSuccess?: (username: string) => void;
}

function messageForError(err: unknown): string {
  if (isApiError(err)) {
    if (err.code === "rate_limited") {
      const retry = err.details?.["retry_after_sec"];
      return typeof retry === "number"
        ? `Too many attempts. Try again in ${retry}s.`
        : "Too many attempts. Please try again later.";
    }
    if (err.code === "unauthorized") {
      return "Invalid username or password.";
    }
    return err.message;
  }
  return "Something went wrong. Please try again.";
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [formError, setFormError] = React.useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: "", password: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const result = await login(values);
      onSuccess?.(result.username);
    } catch (err) {
      setFormError(messageForError(err));
    }
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1">
        <Label htmlFor="username">Username</Label>
        <Input id="username" autoComplete="username" {...register("username")} />
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
          autoComplete="current-password"
          {...register("password")}
        />
        {errors.password && (
          <p role="alert" className="text-sm text-red-600">
            {errors.password.message}
          </p>
        )}
      </div>

      {formError && (
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}

      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Signing in..." : "Sign in"}
      </Button>
    </form>
  );
}
