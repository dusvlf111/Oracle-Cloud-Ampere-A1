/**
 * Protected route group. The session-cookie guard runs in `middleware.ts`
 * (PRD §7.7.4); this layout provides the app chrome (sidebar + header) for all
 * authenticated pages (PRD §7.4).
 */
import { Header } from "@/widgets/header";
import { Sidebar } from "@/widgets/sidebar";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
