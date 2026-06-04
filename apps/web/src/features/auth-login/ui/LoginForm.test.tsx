import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { errorEnvelope } from "../../../../tests/mocks/handlers";
import { server } from "../../../../tests/mocks/server";

import { LoginForm } from "./LoginForm";

const LOGIN = "http://localhost:3000/api/auth/login";

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Username"), "admin");
  await user.type(screen.getByLabelText("Password"), "secret");
}

describe("LoginForm", () => {
  it("calls onSuccess on a successful login", async () => {
    server.use(
      http.post(LOGIN, () => HttpResponse.json({ username: "admin" })),
    );
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<LoginForm onSuccess={onSuccess} />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith("admin"));
  });

  it("shows an error message on 401 unauthorized", async () => {
    server.use(
      http.post(LOGIN, () =>
        HttpResponse.json(
          errorEnvelope("unauthorized", "Invalid credentials"),
          { status: 401 },
        ),
      ),
    );
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<LoginForm onSuccess={onSuccess} />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid username or password/i)).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("shows the pending message on 403 account_pending", async () => {
    server.use(
      http.post(LOGIN, () =>
        HttpResponse.json(
          errorEnvelope("account_pending", "Account awaiting admin approval"),
          { status: 403 },
        ),
      ),
    );
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<LoginForm onSuccess={onSuccess} />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/pending admin approval/i)).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("shows the disabled message on 403 account_disabled", async () => {
    server.use(
      http.post(LOGIN, () =>
        HttpResponse.json(
          errorEnvelope("account_disabled", "Account has been disabled"),
          { status: 403 },
        ),
      ),
    );
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<LoginForm onSuccess={onSuccess} />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/Account disabled/i)).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("shows a rate-limit message on 429 with retry_after_sec", async () => {
    server.use(
      http.post(LOGIN, () =>
        HttpResponse.json(
          errorEnvelope("rate_limited", "Too many login attempts", {
            retry_after_sec: 42,
          }),
          { status: 429 },
        ),
      ),
    );
    const user = userEvent.setup();
    render(<LoginForm />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/try again in 42s/i)).toBeInTheDocument();
  });

  it("blocks submit and shows zod validation errors when fields are empty", async () => {
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<LoginForm onSuccess={onSuccess} />);

    // No MSW handler registered → if a request fired, onUnhandledRequest:'error'
    // would fail the test. Validation must prevent the network call entirely.
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Username is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
