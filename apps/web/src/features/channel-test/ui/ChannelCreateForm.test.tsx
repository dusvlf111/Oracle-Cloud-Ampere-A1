import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { ChannelCreateForm } from "./ChannelCreateForm";

const CREATE = "http://localhost:3000/api/channels";

describe("ChannelCreateForm", () => {
  it("swaps form fields when the type changes", async () => {
    const user = userEvent.setup();
    render(<ChannelCreateForm />);

    // Default discord → webhook field.
    expect(screen.getByLabelText("Webhook URL")).toBeInTheDocument();
    expect(screen.queryByLabelText("Topic")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Type"), "ntfy");
    expect(await screen.findByLabelText("Server URL")).toBeInTheDocument();
    expect(screen.getByLabelText("Topic")).toBeInTheDocument();
    expect(screen.queryByLabelText("Webhook URL")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Type"), "telegram");
    expect(await screen.findByLabelText("Bot token")).toBeInTheDocument();
    expect(screen.getByLabelText("Chat ID")).toBeInTheDocument();
  });

  it("submits an ntfy channel payload with split tags", async () => {
    let body: unknown = null;
    server.use(
      http.post(CREATE, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          {
            id: 2,
            name: "supabin ntfy",
            type: "ntfy",
            enabled: true,
            config: {
              server_url: "https://ntfy.supabin.com",
              topic: "oci-arm-alerts",
              priority: 4,
              tags: ["rocket", "oracle"],
            },
            created_at: "2026-06-03T10:24:00Z",
            updated_at: "2026-06-03T10:24:00Z",
          },
          { status: 201 },
        );
      }),
    );
    const onCreated = vi.fn();
    const user = userEvent.setup();
    render(<ChannelCreateForm onCreated={onCreated} />);

    await user.type(screen.getByLabelText("Name"), "supabin ntfy");
    await user.selectOptions(screen.getByLabelText("Type"), "ntfy");
    await user.type(screen.getByLabelText("Server URL"), "https://ntfy.supabin.com");
    await user.type(screen.getByLabelText("Topic"), "oci-arm-alerts");
    const priority = screen.getByLabelText("Priority (1–5)");
    await user.clear(priority);
    await user.type(priority, "4");
    await user.type(screen.getByLabelText("Tags (comma-separated)"), "rocket, oracle");

    await user.click(screen.getByRole("button", { name: /create channel/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    expect(body).toMatchObject({
      name: "supabin ntfy",
      type: "ntfy",
      config: {
        type: "ntfy",
        server_url: "https://ntfy.supabin.com",
        topic: "oci-arm-alerts",
        priority: 4,
        tags: ["rocket", "oracle"],
      },
    });
  });

  it("blocks submit with validation errors for an invalid webhook URL", async () => {
    const onCreated = vi.fn();
    const user = userEvent.setup();
    render(<ChannelCreateForm onCreated={onCreated} />);

    await user.type(screen.getByLabelText("Name"), "my discord");
    await user.type(screen.getByLabelText("Webhook URL"), "not-a-url");
    await user.click(screen.getByRole("button", { name: /create channel/i }));

    expect(await screen.findByText(/valid webhook url required/i)).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
  });
});
