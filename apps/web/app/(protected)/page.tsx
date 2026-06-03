"use client";

import { useRouter } from "next/navigation";

import { LogoutButton } from "@/features/auth-logout";
import { Button } from "@/shared";

export default function HomePage() {
  const router = useRouter();
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-semibold">OCI Ampere A1 Auto-Provisioner</h1>
      <Button>시작하기</Button>
      <LogoutButton onSuccess={() => router.replace("/login")} />
    </main>
  );
}
