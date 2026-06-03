/**
 * Protected route group. The session-cookie guard runs in `middleware.ts`
 * (PRD §7.7.4); this layout is the thin shell for all authenticated pages.
 */
export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
