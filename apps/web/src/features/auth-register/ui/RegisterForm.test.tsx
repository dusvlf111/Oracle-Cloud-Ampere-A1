import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";
import { errorEnvelope } from "../../../../tests/mocks/handlers";

import { RegisterForm } from "./RegisterForm";

const REGISTER = "http://localhost:3000/api/auth/register";

async function fillAndSubmit(label: RegExp) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Username"), "alice");
  await user.type(screen.getByLabelText("Password"), "password123");
  await user.type(screen.getByLabelText("Confirm password"), "password123");
  await user.click(screen.getByRole("button", { name: label }));
}

describe("RegisterForm", () => {
  it("setup mode: active result triggers auto-login callback", async () => {
    server.use(
      http.post(REGISTER, () =>
        HttpResponse.json(
          { username: "root", role: "admin", status: "active" },
          { status: 201 },
        ),
      ),
    );
    const onAutoLogin = vi.fn();
    const onPending = vi.fn();
    render(
      <RegisterForm mode="setup" onAutoLogin={onAutoLogin} onPending={onPending} />,
    );
    expect(
      screen.getByRole("button", { name: /Create admin account/ }),
    ).toBeInTheDocument();

    await fillAndSubmit(/Create admin account/);

    await waitFor(() => expect(onAutoLogin).toHaveBeenCalledTimes(1));
    expect(onPending).not.toHaveBeenCalled();
  });

  it("signup mode: pending result triggers onPending callback", async () => {
    server.use(
      http.post(REGISTER, () =>
        HttpResponse.json(
          { username: "alice", role: "user", status: "pending" },
          { status: 201 },
        ),
      ),
    );
    const onAutoLogin = vi.fn();
    const onPending = vi.fn();
    render(
      <RegisterForm mode="signup" onAutoLogin={onAutoLogin} onPending={onPending} />,
    );
    expect(screen.getByRole("button", { name: /Sign up/ })).toBeInTheDocument();

    await fillAndSubmit(/Sign up/);

    await waitFor(() => expect(onPending).toHaveBeenCalledTimes(1));
    expect(onPending.mock.calls[0][0]).toMatchObject({ username: "alice" });
    expect(onAutoLogin).not.toHaveBeenCalled();
  });

  it("shows a friendly message on 409 username_taken", async () => {
    server.use(
      http.post(REGISTER, () =>
        HttpResponse.json(errorEnvelope("username_taken", "taken"), {
          status: 409,
        }),
      ),
    );
    render(<RegisterForm mode="signup" />);
    await fillAndSubmit(/Sign up/);

    expect(
      await screen.findByText(/That username is already taken/),
    ).toBeInTheDocument();
  });

  it("validates password confirmation locally", async () => {
    const user = userEvent.setup();
    render(<RegisterForm mode="signup" />);
    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.type(screen.getByLabelText("Confirm password"), "different");
    await user.click(screen.getByRole("button", { name: /Sign up/ }));

    expect(
      await screen.findByText(/Passwords do not match/),
    ).toBeInTheDocument();
  });
});
