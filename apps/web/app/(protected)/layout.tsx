"use client";

/**
 * Protected route group. The session-cookie guard runs in `middleware.ts`
 * (PRD §7.7.4); this layout provides the app chrome (sidebar + header) for all
 * authenticated pages (PRD §7.4).
 *
 * Responsive chrome (Push 7): the sidebar is a static rail from `md` up and a
 * slide-in drawer below `md`, opened by the header hamburger. Drawer open
 * state lives here (the `app` layer) so both same-layer widgets stay decoupled.
 */
import * as React from "react";

import { Header } from "@/widgets/header";
import { Sidebar } from "@/widgets/sidebar";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  return (
    <div className="flex min-h-screen">
      <Sidebar open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header onMenuClick={() => setDrawerOpen(true)} />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
