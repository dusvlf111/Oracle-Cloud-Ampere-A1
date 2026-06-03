import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

import { Header } from "./Header";

function renderHeader(props?: { title?: string; onMenuClick?: () => void }) {
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <Header {...props} />
    </QueryClientProvider>,
  );
}

describe("Header", () => {
  it("renders the default title and a logout button", () => {
    renderHeader();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("renders a custom title", () => {
    renderHeader({ title: "Configs" });
    expect(screen.getByText("Configs")).toBeInTheDocument();
  });

  it("renders a hamburger button that triggers onMenuClick", () => {
    const onMenuClick = vi.fn();
    renderHeader({ onMenuClick });
    const button = screen.getByRole("button", { name: /open navigation/i });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(onMenuClick).toHaveBeenCalledTimes(1);
  });
});
