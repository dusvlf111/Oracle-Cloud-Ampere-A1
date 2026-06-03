import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { LoginPage } from "./LoginPage";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

const SETUP = "http://localhost:3000/api/auth/setup";

describe("LoginPage", () => {
  it("renders the setup form when needs_setup is true", async () => {
    server.use(
      http.get(SETUP, () => HttpResponse.json({ needs_setup: true })),
    );
    render(<LoginPage />);

    expect(
      await screen.findByRole("button", { name: /create admin account/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
  });

  it("renders the login form when needs_setup is false", async () => {
    server.use(
      http.get(SETUP, () => HttpResponse.json({ needs_setup: false })),
    );
    render(<LoginPage />);

    expect(
      await screen.findByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Confirm password")).not.toBeInTheDocument();
  });
});
