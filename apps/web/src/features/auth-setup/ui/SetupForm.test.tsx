import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { errorEnvelope } from "../../../../tests/mocks/handlers";
import { server } from "../../../../tests/mocks/server";

import { SetupForm } from "./SetupForm";

const SETUP = "http://localhost:3000/api/auth/setup";

async function fill(
  user: ReturnType<typeof userEvent.setup>,
  { confirm = "sup3r-secret" }: { confirm?: string } = {},
) {
  await user.type(screen.getByLabelText("Username"), "operator");
  await user.type(screen.getByLabelText("Password"), "sup3r-secret");
  await user.type(screen.getByLabelText("Confirm password"), confirm);
}

describe("SetupForm", () => {
  it("creates the admin and calls onSuccess on success", async () => {
    server.use(
      http.post(SETUP, () => HttpResponse.json({ username: "operator" })),
    );
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<SetupForm onSuccess={onSuccess} />);

    await fill(user);
    await user.click(
      screen.getByRole("button", { name: /create admin account/i }),
    );

    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith("operator"));
  });

  it("shows a confirm error when passwords do not match", async () => {
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<SetupForm onSuccess={onSuccess} />);

    // No POST handler registered: validation must block the network call
    // (onUnhandledRequest:'error' would otherwise fail the test).
    await fill(user, { confirm: "different-pw" });
    await user.click(
      screen.getByRole("button", { name: /create admin account/i }),
    );

    expect(
      await screen.findByText("Passwords do not match"),
    ).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("shows a validation message on 422 from the server", async () => {
    server.use(
      http.post(SETUP, () =>
        HttpResponse.json(
          errorEnvelope("validation_error", "Request validation failed"),
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    render(<SetupForm />);

    await fill(user);
    await user.click(
      screen.getByRole("button", { name: /create admin account/i }),
    );

    expect(
      await screen.findByText(/request validation failed/i),
    ).toBeInTheDocument();
  });

  it("shows an already-exists message on 409 setup_already_done", async () => {
    server.use(
      http.post(SETUP, () =>
        HttpResponse.json(
          errorEnvelope("setup_already_done", "Admin account already exists"),
          { status: 409 },
        ),
      ),
    );
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<SetupForm onSuccess={onSuccess} />);

    await fill(user);
    await user.click(
      screen.getByRole("button", { name: /create admin account/i }),
    );

    expect(
      await screen.findByText(/admin already exists\. please sign in\./i),
    ).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
