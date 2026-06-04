import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";

let mockPathname = "/configs";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    onClick,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    onClick?: () => void;
  }) => (
    <a href={href} onClick={onClick} {...rest}>
      {children}
    </a>
  ),
}));

import { NAV_ITEMS, Sidebar } from "./Sidebar";

const ME = "http://localhost:3000/api/auth/me";

function seedSession(role: "admin" | "user") {
  server.use(
    http.get(ME, () =>
      HttpResponse.json({ username: "u", role, status: "active" }),
    ),
  );
}

/** Render the sidebar inside a QueryClientProvider (session hook needs it). */
function renderSidebar(props?: React.ComponentProps<typeof Sidebar>) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return render(<Sidebar {...props} />, { wrapper });
}

afterEach(() => {
  mockPathname = "/configs";
});

describe("Sidebar", () => {
  it("renders a link for every non-admin nav item with correct hrefs", () => {
    seedSession("user");
    renderSidebar();
    for (const item of NAV_ITEMS.filter((i) => !i.adminOnly)) {
      const links = screen.getAllByRole("link", {
        name: new RegExp(item.label, "i"),
      });
      expect(links[0]).toHaveAttribute("href", item.href);
    }
  });

  it("shows the 유저 관리 link for an admin session only", async () => {
    seedSession("admin");
    renderSidebar();
    await waitFor(() =>
      expect(screen.getAllByRole("link", { name: /유저 관리/ }).length).toBeGreaterThan(0),
    );
    expect(
      screen.getAllByRole("link", { name: /유저 관리/ })[0],
    ).toHaveAttribute("href", "/users");
  });

  it("hides the 유저 관리 link for a non-admin session", async () => {
    seedSession("user");
    renderSidebar();
    // Wait for the session to resolve, then assert the admin link is absent.
    await waitFor(() =>
      expect(screen.getAllByRole("link", { name: /configs/i }).length).toBeGreaterThan(0),
    );
    expect(screen.queryByRole("link", { name: /유저 관리/ })).toBeNull();
  });

  it("marks the active route via aria-current", () => {
    seedSession("admin");
    renderSidebar();
    const active = screen.getAllByRole("link", { name: /configs/i })[0];
    expect(active).toHaveAttribute("aria-current", "page");
    const inactive = screen.getAllByRole("link", { name: /dashboard/i })[0];
    expect(inactive).not.toHaveAttribute("aria-current");
  });

  it("reflects the drawer open state on the drawer panel", () => {
    seedSession("admin");
    const { rerender } = renderSidebar({ open: false, onClose: vi.fn() });
    const drawer = screen.getByTestId("sidebar-drawer");
    expect(drawer.className).toContain("-translate-x-full");

    rerender(<Sidebar open onClose={vi.fn()} />);
    expect(screen.getByTestId("sidebar-drawer").className).toContain("translate-x-0");
  });

  it("calls onClose when the overlay is clicked", () => {
    seedSession("admin");
    const onClose = vi.fn();
    renderSidebar({ open: true, onClose });
    fireEvent.click(screen.getByTestId("sidebar-overlay"));
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when a drawer link is clicked", () => {
    seedSession("admin");
    const onClose = vi.fn();
    renderSidebar({ open: true, onClose });
    onClose.mockClear(); // ignore the mount effect call
    const drawer = screen.getByTestId("sidebar-drawer");
    const link = drawer.querySelector("a")!;
    fireEvent.click(link);
    expect(onClose).toHaveBeenCalled();
  });

  it("auto-closes when the route changes", () => {
    seedSession("admin");
    const onClose = vi.fn();
    const { rerender } = renderSidebar({ open: true, onClose });
    onClose.mockClear();

    mockPathname = "/logs";
    rerender(<Sidebar open onClose={onClose} />);
    expect(onClose).toHaveBeenCalled();
  });
});
