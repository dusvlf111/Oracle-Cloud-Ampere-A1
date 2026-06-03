import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { configsQueryKey, type Config } from "@/entities/config";

import { server } from "../../../../tests/mocks/server";

import { ConfigToggle } from "./ConfigToggle";

const TOGGLE = "http://localhost:3000/api/configs/5/toggle";

function makeConfig(over: Partial<Config> = {}): Config {
  return {
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
    channel_ids: [],
    created_at: "2026-06-03T10:24:00Z",
    updated_at: "2026-06-03T10:24:00Z",
    ...over,
  };
}

describe("ConfigToggle", () => {
  it("optimistically flips the cached enabled flag then settles on server state", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const key = configsQueryKey();
    client.setQueryData<Config[]>(key, [makeConfig({ enabled: true })]);

    const gate: { resolve: (() => void) | null } = { resolve: null };
    server.use(
      http.post(TOGGLE, async () => {
        await new Promise<void>((r) => {
          gate.resolve = r;
        });
        return HttpResponse.json(makeConfig({ enabled: false }));
      }),
    );

    const user = userEvent.setup();
    render(
      <QueryClientProvider client={client}>
        <ConfigToggle configId={5} enabled={true} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Disable" }));

    // Optimistic update applied before the request resolves.
    await waitFor(() =>
      expect(client.getQueryData<Config[]>(key)?.[0].enabled).toBe(false),
    );

    gate.resolve?.();
  });

  it("rolls back the optimistic update on error", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const key = configsQueryKey();
    client.setQueryData<Config[]>(key, [makeConfig({ enabled: true })]);

    server.use(
      http.post(TOGGLE, () => new HttpResponse(null, { status: 500 })),
      // invalidation refetch after settle:
      http.get("http://localhost:3000/api/configs", () =>
        HttpResponse.json([makeConfig({ enabled: true })]),
      ),
    );

    const user = userEvent.setup();
    render(
      <QueryClientProvider client={client}>
        <ConfigToggle configId={5} enabled={true} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Disable" }));

    await waitFor(() =>
      expect(client.getQueryData<Config[]>(key)?.[0].enabled).toBe(true),
    );
  });
});
