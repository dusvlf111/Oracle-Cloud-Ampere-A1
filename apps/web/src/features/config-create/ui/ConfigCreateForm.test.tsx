import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { ConfigCreateForm } from "./ConfigCreateForm";

import type { Config } from "@/entities/config";

const EXISTING: Config = {
  id: 5,
  name: "ARM main",
  credential_id: 1,
  enabled: true,
  shape: "VM.Standard.A1.Flex",
  ocpus: 2,
  memory_gb: 12,
  boot_volume_gb: 100,
  image_ocid: "ocid1.image.oc1..aaaaubuntu",
  subnet_ocid: "ocid1.subnet.oc1..aaaapub",
  availability_domain: "Uocm:AP-CHUNCHEON-1-AD-1",
  ssh_public_key: "ssh-ed25519 AAA",
  retry_interval_sec: 120,
  max_attempts: 500,
  channel_ids: [7],
  created_at: "2026-06-03T10:24:00Z",
  updated_at: "2026-06-03T10:24:00Z",
};

const CREDS = "http://localhost:3000/api/credentials";
const CHANS = "http://localhost:3000/api/channels";
const CONFIGS = "http://localhost:3000/api/configs";
const META_AD = "http://localhost:3000/api/meta/availability-domains";
const META_IMAGES = "http://localhost:3000/api/meta/images";
const META_SUBNETS = "http://localhost:3000/api/meta/subnets";

const IMAGE_OCID = "ocid1.image.oc1..aaaaubuntu";
const SUBNET_OCID = "ocid1.subnet.oc1..aaaapub";
const AD_NAME = "Uocm:AP-CHUNCHEON-1-AD-1";

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

function seedMetaSuccess() {
  server.use(
    http.get(META_AD, () => HttpResponse.json([AD_NAME])),
    http.get(META_IMAGES, () =>
      HttpResponse.json([
        {
          ocid: IMAGE_OCID,
          display_name: "Canonical-Ubuntu-22.04-aarch64",
          operating_system: "Canonical Ubuntu",
          os_version: "22.04",
        },
      ]),
    ),
    http.get(META_SUBNETS, () =>
      HttpResponse.json([
        {
          ocid: SUBNET_OCID,
          display_name: "public-subnet",
          cidr_block: "10.0.0.0/24",
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

    await user.click(screen.getByRole("button", { name: /create config/i }));

    expect(await screen.findByText("Name is required")).toBeInTheDocument();
    expect(screen.getByText("Image OCID is required")).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("populates meta dropdowns and submits the selected OCID values", async () => {
    seedLists();
    seedMetaSuccess();
    type Body = {
      channel_ids?: number[];
      credential_id?: number;
      image_ocid?: string;
      subnet_ocid?: string;
      availability_domain?: string;
    };
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
            image_ocid: IMAGE_OCID,
            subnet_ocid: SUBNET_OCID,
            availability_domain: AD_NAME,
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

    await screen.findByRole("option", { name: "main" });

    await user.type(screen.getByLabelText("Name"), "ARM main");
    await user.selectOptions(screen.getByLabelText("Credential"), "1");
    await user.type(screen.getByLabelText("SSH public key"), "ssh-ed25519 AAA");
    await user.click(screen.getByLabelText("supabin ntfy"));

    // Once a credential is chosen the meta lookups fire and fill the dropdowns.
    await screen.findByRole("option", {
      name: "Canonical-Ubuntu-22.04-aarch64 (22.04)",
    });
    await screen.findByRole("option", { name: "public-subnet (10.0.0.0/24)" });
    await screen.findByRole("option", { name: AD_NAME });

    await user.selectOptions(screen.getByLabelText("Availability domain"), AD_NAME);
    await user.selectOptions(screen.getByLabelText("Image OCID"), IMAGE_OCID);
    await user.selectOptions(screen.getByLabelText("Subnet OCID"), SUBNET_OCID);

    await user.click(screen.getByRole("button", { name: /create config/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    expect(captured.body?.credential_id).toBe(1);
    expect(captured.body?.image_ocid).toBe(IMAGE_OCID);
    expect(captured.body?.subnet_ocid).toBe(SUBNET_OCID);
    expect(captured.body?.availability_domain).toBe(AD_NAME);
    expect(captured.body?.channel_ids).toEqual([7]);
  });

  it("renders fixed-choice fields as dropdowns with default values", async () => {
    seedLists();
    renderForm();

    const ocpus = (await screen.findByLabelText("OCPUs")) as HTMLSelectElement;
    expect(ocpus.tagName).toBe("SELECT");
    expect(ocpus.value).toBe("4");

    const memory = screen.getByLabelText("Memory (GB)") as HTMLSelectElement;
    expect(memory.tagName).toBe("SELECT");
    expect(memory.value).toBe("24");

    const boot = screen.getByLabelText("Boot volume (GB)") as HTMLSelectElement;
    expect(boot.value).toBe("50");

    const retry = screen.getByLabelText("Retry interval") as HTMLSelectElement;
    expect(retry.value).toBe("60");

    const maxAttempts = screen.getByLabelText("Max attempts") as HTMLSelectElement;
    // Unlimited default → empty value.
    expect(maxAttempts.value).toBe("");

    // OCPU × 6 memory hint reflects the default 4 OCPUs.
    expect(screen.getByText(/Recommended: OCPU × 6 = 24 GB/)).toBeInTheDocument();
  });

  it("submits dropdown selections (ocpu/memory/boot/retry/max) as numbers", async () => {
    seedLists();
    seedMetaSuccess();
    type Body = {
      ocpus?: number;
      memory_gb?: number;
      boot_volume_gb?: number;
      retry_interval_sec?: number;
      max_attempts?: number | null;
    };
    const captured: { body: Body | null } = { body: null };
    server.use(
      http.post(CONFIGS, async ({ request }) => {
        captured.body = (await request.json()) as Body;
        return HttpResponse.json({ id: 9 }, { status: 201 });
      }),
    );
    renderForm();
    const user = userEvent.setup();

    await screen.findByRole("option", { name: "main" });
    await user.type(screen.getByLabelText("Name"), "tuned");
    await user.selectOptions(screen.getByLabelText("Credential"), "1");
    await user.type(screen.getByLabelText("SSH public key"), "ssh-ed25519 AAA");

    await user.selectOptions(screen.getByLabelText("OCPUs"), "2");
    await user.selectOptions(screen.getByLabelText("Memory (GB)"), "12");
    await user.selectOptions(screen.getByLabelText("Boot volume (GB)"), "100");
    await user.selectOptions(screen.getByLabelText("Retry interval"), "120");
    await user.selectOptions(screen.getByLabelText("Max attempts"), "500");

    await screen.findByRole("option", { name: AD_NAME });
    await user.selectOptions(screen.getByLabelText("Availability domain"), AD_NAME);
    await user.selectOptions(screen.getByLabelText("Image OCID"), IMAGE_OCID);
    await user.selectOptions(screen.getByLabelText("Subnet OCID"), SUBNET_OCID);

    await user.click(screen.getByRole("button", { name: /create config/i }));

    await waitFor(() => expect(captured.body).not.toBeNull());
    expect(captured.body?.ocpus).toBe(2);
    expect(captured.body?.memory_gb).toBe(12);
    expect(captured.body?.boot_volume_gb).toBe(100);
    expect(captured.body?.retry_interval_sec).toBe(120);
    expect(captured.body?.max_attempts).toBe(500);
  });

  it("prefills from an existing config and PUTs on edit", async () => {
    seedLists();
    seedMetaSuccess();
    type Body = { name?: string; ocpus?: number; max_attempts?: number | null };
    const captured: { body: Body | null; id: string | null } = {
      body: null,
      id: null,
    };
    server.use(
      http.put(`${CONFIGS}/:id`, async ({ request, params }) => {
        captured.body = (await request.json()) as Body;
        captured.id = params.id as string;
        return HttpResponse.json({ ...EXISTING, name: "renamed" });
      }),
    );

    const onSaved = vi.fn();
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <ConfigCreateForm mode="edit" initial={EXISTING} onSaved={onSaved} />
      </QueryClientProvider>,
    );
    const user = userEvent.setup();

    // Prefilled values from the existing config.
    expect((await screen.findByLabelText("Name")) as HTMLInputElement).toHaveValue(
      "ARM main",
    );
    expect((screen.getByLabelText("OCPUs") as HTMLSelectElement).value).toBe("2");
    expect((screen.getByLabelText("Max attempts") as HTMLSelectElement).value).toBe(
      "500",
    );

    // Button reflects edit mode.
    const save = screen.getByRole("button", { name: /save changes/i });

    const name = screen.getByLabelText("Name");
    await user.clear(name);
    await user.type(name, "renamed");
    await user.click(save);

    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(captured.id).toBe("5");
    expect(captured.body?.name).toBe("renamed");
    expect(captured.body?.ocpus).toBe(2);
    expect(captured.body?.max_attempts).toBe(500);
  });

  it("falls back to manual text input when a meta lookup fails (502)", async () => {
    seedLists();
    server.use(
      http.get(META_AD, () => HttpResponse.json([AD_NAME])),
      http.get(META_SUBNETS, () =>
        HttpResponse.json([
          { ocid: SUBNET_OCID, display_name: "public-subnet", cidr_block: "10.0.0.0/24" },
        ]),
      ),
      // Image lookup fails → field must auto-switch to manual entry.
      http.get(META_IMAGES, () =>
        HttpResponse.json(
          {
            error: {
              code: "oci_request_failed",
              message: "boom",
              details: null,
              request_id: "01TEST",
            },
          },
          { status: 502 },
        ),
      ),
    );
    type Body = { image_ocid?: string };
    const captured: { body: Body | null } = { body: null };
    server.use(
      http.post(CONFIGS, async ({ request }) => {
        captured.body = (await request.json()) as Body;
        return HttpResponse.json(
          {
            id: 6,
            name: "manual img",
            credential_id: 1,
            enabled: true,
            shape: "VM.Standard.A1.Flex",
            ocpus: 4,
            memory_gb: 24,
            boot_volume_gb: 50,
            image_ocid: "ocid1.image.manual",
            subnet_ocid: SUBNET_OCID,
            availability_domain: AD_NAME,
            ssh_public_key: "ssh-ed25519 AAA",
            retry_interval_sec: 60,
            max_attempts: null,
            channel_ids: [],
            created_at: "2026-06-03T10:24:00Z",
            updated_at: "2026-06-03T10:24:00Z",
          },
          { status: 201 },
        );
      }),
    );
    const onCreated = renderForm();
    const user = userEvent.setup();

    await screen.findByRole("option", { name: "main" });
    await user.type(screen.getByLabelText("Name"), "manual img");
    await user.selectOptions(screen.getByLabelText("Credential"), "1");
    await user.type(screen.getByLabelText("SSH public key"), "ssh-ed25519 AAA");

    // Image lookup error surfaces and forces manual input.
    expect(
      await screen.findByText(/OCI lookup failed/),
    ).toBeInTheDocument();

    // The Image field is now a free-text input (role textbox), not a select.
    const imageInput = screen.getByLabelText("Image OCID");
    expect(imageInput.tagName).toBe("INPUT");
    await user.type(imageInput, "ocid1.image.manual");

    // The other (successful) dropdowns still work.
    await screen.findByRole("option", { name: "public-subnet (10.0.0.0/24)" });
    await user.selectOptions(screen.getByLabelText("Subnet OCID"), SUBNET_OCID);
    await user.selectOptions(screen.getByLabelText("Availability domain"), AD_NAME);

    await user.click(screen.getByRole("button", { name: /create config/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    expect(captured.body?.image_ocid).toBe("ocid1.image.manual");
  });
});
