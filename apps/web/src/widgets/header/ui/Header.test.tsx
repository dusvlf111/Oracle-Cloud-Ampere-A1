import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

import { Header } from "./Header";

function renderHeader(title?: string) {
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <Header title={title} />
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
    renderHeader("Configs");
    expect(screen.getByText("Configs")).toBeInTheDocument();
  });
});
