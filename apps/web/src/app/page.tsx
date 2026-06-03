import { Button } from "@/shared/ui";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-semibold">OCI Ampere A1 Auto-Provisioner</h1>
      <Button>시작하기</Button>
    </main>
  );
}
