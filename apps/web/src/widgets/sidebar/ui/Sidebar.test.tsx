import { render, screen } from "@testing-library/react";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/configs",
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { NAV_ITEMS, Sidebar } from "./Sidebar";

describe("Sidebar", () => {
  it("renders a link for every nav item with correct hrefs", () => {
    render(<Sidebar />);
    for (const item of NAV_ITEMS) {
      const link = screen.getByRole("link", { name: new RegExp(item.label, "i") });
      expect(link).toHaveAttribute("href", item.href);
    }
  });

  it("marks the active route via aria-current", () => {
    render(<Sidebar />);
    const active = screen.getByRole("link", { name: /configs/i });
    expect(active).toHaveAttribute("aria-current", "page");
    const inactive = screen.getByRole("link", { name: /dashboard/i });
    expect(inactive).not.toHaveAttribute("aria-current");
  });
});
