"use client";

import { useRouter } from "next/navigation";

import { LoginForm } from "@/features/auth-login";

export function LoginPage() {
  const router = useRouter();
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-6 p-6">
      <h1 className="text-center text-2xl font-semibold">Sign in</h1>
      <LoginForm onSuccess={() => router.replace("/")} />
    </main>
  );
}
