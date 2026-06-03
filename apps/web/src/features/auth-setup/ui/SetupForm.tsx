"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import * as React from "react";
import { useForm } from "react-hook-form";

import { Button, Input, Label, isApiError } from "@/shared";

import { createAdmin } from "../model/setup";
import { setupSchema, type SetupValues } from "../model/schema";

export interface SetupFormProps {
  /** Called after the admin is created + auto-logged-in (e.g. router.replace('/')). */
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
    if (err.code === "setup_already_done") {
      return "Admin already exists. Please sign in.";
    }
    return err.message;
  }
  return "Something went wrong. Please try again.";
}

export function SetupForm({ onSuccess }: SetupFormProps) {
  const [formError, setFormError] = React.useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SetupValues>({
    resolver: zodResolver(setupSchema),
    defaultValues: { username: "", password: "", confirm: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const result = await createAdmin({
        username: values.username,
        password: values.password,
      });
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
          autoComplete="new-password"
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

      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating account..." : "Create admin account"}
      </Button>
    </form>
  );
}
