"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { LoginForm } from "@/features/auth-login";
import { SetupForm, getSetupStatus } from "@/features/auth-setup";

type Mode = "loading" | "setup" | "login";

export function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = React.useState<Mode>("loading");

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
      {mode === "loading" ? (
        <p className="text-center text-sm text-muted-foreground">Loading...</p>
      ) : mode === "setup" ? (
        <>
          <h1 className="text-center text-2xl font-semibold">
            Create admin account
          </h1>
          <SetupForm onSuccess={goHome} />
        </>
      ) : (
        <>
          <h1 className="text-center text-2xl font-semibold">Sign in</h1>
          <LoginForm onSuccess={goHome} />
        </>
      )}
    </main>
  );
}
