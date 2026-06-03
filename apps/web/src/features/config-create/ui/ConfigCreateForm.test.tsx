import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { ConfigCreateForm } from "./ConfigCreateForm";

const CREDS = "http://localhost:3000/api/credentials";
const CHANS = "http://localhost:3000/api/channels";
const CONFIGS = "http://localhost:3000/api/configs";

function renderForm(onCreated = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ConfigCreateForm onCreated={onCreated} />
    </QueryClientProvider>,
  );
  return onCreated;
}

function seedLists() {
  server.use(
    http.get(CREDS, () =>
      HttpResponse.json([
        {
          id: 1,
          name: "main",
          tenancy_ocid: "x",
          user_ocid: "x",
          fingerprint: "x",
          region: "ap-chuncheon-1",
          has_passphrase: false,
          created_at: "2026-06-03T10:23:45Z",
        },
      ]),
    ),
    http.get(CHANS, () =>
      HttpResponse.json([
        {
          id: 7,
          name: "supabin ntfy",
          type: "ntfy",
          enabled: true,
          config: {},
          created_at: "2026-06-03T10:24:00Z",
          updated_at: "2026-06-03T10:24:00Z",
        },
      ]),
    ),
  );
}

describe("ConfigCreateForm", () => {
  it("blocks submit and shows validation errors for missing required fields", async () => {
    seedLists();
    const onCreated = renderForm();
    const user = userEvent.setup();

    // credential select + ocids + ssh key empty → validation must block.
    await user.click(screen.getByRole("button", { name: /create config/i }));

    expect(await screen.findByText("Name is required")).toBeInTheDocument();
    expect(screen.getByText("Image OCID is required")).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("submits with selected credential and channel_ids", async () => {
    seedLists();
    type Body = { channel_ids?: number[]; credential_id?: number };
    const captured: { body: Body | null } = { body: null };
    server.use(
      http.post(CONFIGS, async ({ request }) => {
        captured.body = (await request.json()) as Body;
        return HttpResponse.json(
          {
            id: 5,
            name: "ARM main",
            credential_id: 1,
            enabled: true,
            shape: "VM.Standard.A1.Flex",
            ocpus: 4,
            memory_gb: 24,
            boot_volume_gb: 50,
            image_ocid: "ocid1.image",
            subnet_ocid: "ocid1.subnet",
            availability_domain: "AD-1",
            ssh_public_key: "ssh-ed25519 AAA",
            retry_interval_sec: 60,
            max_attempts: null,
            channel_ids: [7],
            created_at: "2026-06-03T10:24:00Z",
            updated_at: "2026-06-03T10:24:00Z",
          },
          { status: 201 },
        );
      }),
    );
    const onCreated = renderForm();
    const user = userEvent.setup();

    // Wait for async credential/channel lists to populate.
    await screen.findByRole("option", { name: "main" });

    await user.type(screen.getByLabelText("Name"), "ARM main");
    await user.selectOptions(screen.getByLabelText("Credential"), "1");
    await user.type(screen.getByLabelText("Image OCID"), "ocid1.image");
    await user.type(screen.getByLabelText("Subnet OCID"), "ocid1.subnet");
    await user.type(screen.getByLabelText("Availability domain"), "AD-1");
    await user.type(screen.getByLabelText("SSH public key"), "ssh-ed25519 AAA");
    await user.click(screen.getByLabelText("supabin ntfy"));

    await user.click(screen.getByRole("button", { name: /create config/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    expect(captured.body?.credential_id).toBe(1);
    expect(captured.body?.channel_ids).toEqual([7]);
  });
});
