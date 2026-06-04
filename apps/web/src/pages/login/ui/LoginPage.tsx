"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { LoginForm } from "@/features/auth-login";
import {
  PendingNotice,
  RegisterForm,
  getSetupStatus,
} from "@/features/auth-register";
import { Button } from "@/shared";

type Mode = "loading" | "setup" | "login" | "signup" | "pending";

export function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = React.useState<Mode>("loading");
  const [pendingUser, setPendingUser] = React.useState<string | undefined>();

  React.useEffect(() => {
    let active = true;
    getSetupStatus()
      .then((status) => {
        if (active) setMode(status.needs_setup ? "setup" : "login");
      })
      .catch(() => {
        // On any failure resolving setup state, fall back to the login form.
        if (active) setMode("login");
      });
    return () => {
      active = false;
    };
  }, []);

  const goHome = () => router.replace("/");

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-6 p-6">
      {mode === "loading" && (
        <p className="text-center text-sm text-muted-foreground">Loading...</p>
      )}

      {mode === "setup" && (
        <>
          {/* First-ever signup keeps the original "관리자 계정 생성" framing and
              auto-logs-in on success (PRD §6.1). */}
          <h1 className="text-center text-2xl font-semibold">관리자 계정 생성</h1>
          <RegisterForm mode="setup" onAutoLogin={goHome} />
        </>
      )}

      {mode === "login" && (
        <>
          <h1 className="text-center text-2xl font-semibold">Sign in</h1>
          <LoginForm onSuccess={goHome} />
          <p className="text-center text-sm text-gray-600">
            계정이 없으신가요?{" "}
            <button
              type="button"
              className="font-medium text-blue-700 underline"
              onClick={() => setMode("signup")}
            >
              가입 신청
            </button>
          </p>
        </>
      )}

      {mode === "signup" && (
        <>
          <h1 className="text-center text-2xl font-semibold">가입 신청</h1>
          <RegisterForm
            mode="signup"
            onAutoLogin={goHome}
            onPending={(r) => {
              setPendingUser(r.username);
              setMode("pending");
            }}
          />
          <Button
            type="button"
            variant="outline"
            className="min-h-11"
            onClick={() => setMode("login")}
          >
            로그인 화면으로
          </Button>
        </>
      )}

      {mode === "pending" && (
        <PendingNotice
          username={pendingUser}
          onBackToLogin={() => setMode("login")}
        />
      )}
    </main>
  );
}
