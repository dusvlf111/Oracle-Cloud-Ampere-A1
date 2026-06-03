import { fireEvent, render, screen } from "@testing-library/react";
import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

afterEach(() => {
  mockPathname = "/configs";
});

describe("Sidebar", () => {
  it("renders a link for every nav item with correct hrefs", () => {
    render(<Sidebar />);
    for (const item of NAV_ITEMS) {
      // Two presentations (rail + drawer) render the same links; pick the first.
      const links = screen.getAllByRole("link", {
        name: new RegExp(item.label, "i"),
      });
      expect(links[0]).toHaveAttribute("href", item.href);
    }
  });

  it("marks the active route via aria-current", () => {
    render(<Sidebar />);
    const active = screen.getAllByRole("link", { name: /configs/i })[0];
    expect(active).toHaveAttribute("aria-current", "page");
    const inactive = screen.getAllByRole("link", { name: /dashboard/i })[0];
    expect(inactive).not.toHaveAttribute("aria-current");
  });

  it("reflects the drawer open state on the drawer panel", () => {
    const { rerender } = render(<Sidebar open={false} onClose={vi.fn()} />);
    const drawer = screen.getByTestId("sidebar-drawer");
    expect(drawer.className).toContain("-translate-x-full");

    rerender(<Sidebar open onClose={vi.fn()} />);
    expect(screen.getByTestId("sidebar-drawer").className).toContain("translate-x-0");
  });

  it("calls onClose when the overlay is clicked", () => {
    const onClose = vi.fn();
    render(<Sidebar open onClose={onClose} />);
    fireEvent.click(screen.getByTestId("sidebar-overlay"));
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when a drawer link is clicked", () => {
    const onClose = vi.fn();
    render(<Sidebar open onClose={onClose} />);
    onClose.mockClear(); // ignore the mount effect call
    const drawer = screen.getByTestId("sidebar-drawer");
    const link = drawer.querySelector("a")!;
    fireEvent.click(link);
    expect(onClose).toHaveBeenCalled();
  });

  it("auto-closes when the route changes", () => {
    const onClose = vi.fn();
    const { rerender } = render(<Sidebar open onClose={onClose} />);
    onClose.mockClear();

    mockPathname = "/logs";
    rerender(<Sidebar open onClose={onClose} />);
    expect(onClose).toHaveBeenCalled();
  });
});
