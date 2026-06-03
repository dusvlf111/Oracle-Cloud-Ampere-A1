import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { DashboardPage } from "./DashboardPage";

const CONFIGS = "http://localhost:3000/api/configs";
const ATTEMPTS = "http://localhost:3000/api/attempts";

function config(id: number, enabled: boolean) {
  return {
    id,
    name: `cfg${id}`,
    credential_id: 1,
    enabled,
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
  };
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  it("aggregates active/inactive config counts", async () => {
    server.use(
      http.get(CONFIGS, () =>
        HttpResponse.json([config(1, true), config(2, true), config(3, false)]),
      ),
      http.get(ATTEMPTS, () => HttpResponse.json([])),
    );
    renderPage();

    await waitFor(() =>
      expect(within(screen.getByTestId("stat-active")).getByText("2")).toBeInTheDocument(),
    );
    expect(within(screen.getByTestId("stat-inactive")).getByText("1")).toBeInTheDocument();
    expect(within(screen.getByTestId("stat-total")).getByText("3")).toBeInTheDocument();
  });

  it("renders the latest successful instance card", async () => {
    server.use(
      http.get(CONFIGS, () => HttpResponse.json([])),
      http.get(ATTEMPTS, ({ request }) => {
        const url = new URL(request.url);
        if (url.searchParams.get("status") === "success") {
          return HttpResponse.json([
            {
              id: 99,
              config_id: 5,
              attempted_at: "2026-06-03T10:30:00Z",
              status: "success",
              instance_ocid: "ocid1.instance..created",
              duration_ms: 3000,
              message: null,
            },
          ]);
        }
        return HttpResponse.json([]);
      }),
    );
    renderPage();

    const card = await screen.findByTestId("success-card");
    expect(within(card).getByText(/ocid1.instance..created/)).toBeInTheDocument();
  });
});
