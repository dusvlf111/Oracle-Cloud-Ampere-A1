import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { LoginPage } from "./LoginPage";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
}));

beforeEach(() => {
  replace.mockClear();
});

const SETUP = "http://localhost:3000/api/auth/setup";
const REGISTER = "http://localhost:3000/api/auth/register";

describe("LoginPage", () => {
  it("renders the admin-create form when needs_setup is true", async () => {
    server.use(http.get(SETUP, () => HttpResponse.json({ needs_setup: true })));
    render(<LoginPage />);

    expect(
      await screen.findByRole("button", { name: /Create admin account/ }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
  });

  it("first signup auto-logs-in and redirects home", async () => {
    server.use(
      http.get(SETUP, () => HttpResponse.json({ needs_setup: true })),
      http.post(REGISTER, () =>
        HttpResponse.json(
          { username: "root", role: "admin", status: "active" },
          { status: 201 },
        ),
      ),
    );
    const user = userEvent.setup();
    render(<LoginPage />);

    await screen.findByRole("button", { name: /Create admin account/ });
    await user.type(screen.getByLabelText("Username"), "root");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.type(screen.getByLabelText("Confirm password"), "password123");
    await user.click(screen.getByRole("button", { name: /Create admin account/ }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });

  it("renders the login form when needs_setup is false", async () => {
    server.use(http.get(SETUP, () => HttpResponse.json({ needs_setup: false })));
    render(<LoginPage />);

    expect(
      await screen.findByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Confirm password")).not.toBeInTheDocument();
  });

  it("subsequent signup shows the pending notice", async () => {
    server.use(
      http.get(SETUP, () => HttpResponse.json({ needs_setup: false })),
      http.post(REGISTER, () =>
        HttpResponse.json(
          { username: "alice", role: "user", status: "pending" },
          { status: 201 },
        ),
      ),
    );
    const user = userEvent.setup();
    render(<LoginPage />);

    await screen.findByRole("button", { name: /sign in/i });
    // Switch to signup mode via the toggle link.
    await user.click(screen.getByRole("button", { name: /Sign up/ }));
    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.type(screen.getByLabelText("Confirm password"), "password123");
    // In signup mode the only "Sign up" button is the form submit.
    await user.click(screen.getByRole("button", { name: /Sign up/ }));

    expect(await screen.findByTestId("pending-notice")).toBeInTheDocument();
    expect(screen.getByText(/Your account is pending approval/)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
