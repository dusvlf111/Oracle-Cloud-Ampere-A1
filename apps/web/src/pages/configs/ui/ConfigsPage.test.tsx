import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { ConfigsPage } from "./ConfigsPage";

const API = "http://localhost:3000/api/configs";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ConfigsPage />
    </QueryClientProvider>,
  );
}

function config(id: number, name: string, enabled = true) {
  return {
    id,
    name,
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

describe("ConfigsPage", () => {
  it("lists configs and toggles one (optimistic + server response)", async () => {
    let enabled = true;
    server.use(
      http.get(API, () => HttpResponse.json([config(5, "ARM main", enabled)])),
      http.post(`${API}/5/toggle`, () => {
        enabled = !enabled;
        return HttpResponse.json(config(5, "ARM main", enabled));
      }),
    );
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("ARM main");
    expect(screen.getByTestId("config-enabled-badge")).toHaveTextContent("enabled");

    await user.click(screen.getByRole("button", { name: "Disable" }));
    await waitFor(() =>
      expect(screen.getByTestId("config-enabled-badge")).toHaveTextContent(
        "disabled",
      ),
    );
  });

  it("deletes a config via the confirm dialog", async () => {
    let deleted = false;
    server.use(
      http.get(API, () =>
        HttpResponse.json(deleted ? [] : [config(5, "ARM main")]),
      ),
      http.delete(`${API}/5`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("ARM main");
    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", {
      name: /confirm delete config/i,
    });
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("deleted"),
    );
    await waitFor(() =>
      expect(screen.queryByText("ARM main")).not.toBeInTheDocument(),
    );
  });

  it("renders the config row stacked on mobile (responsive)", async () => {
    server.use(http.get(API, () => HttpResponse.json([config(5, "ARM main")])));
    renderPage();
    await screen.findByText("ARM main");
    const row = screen.getByTestId("config-row");
    expect(row.className).toContain("flex-col");
    expect(row.className).toContain("sm:flex-row");
  });

  it("renders the confirm dialog as a mobile bottom sheet (responsive)", async () => {
    server.use(http.get(API, () => HttpResponse.json([config(5, "ARM main")])));
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("ARM main");
    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", { name: /confirm delete config/i });
    const panel = dialog.querySelector("div")!;
    expect(panel.className).toContain("w-full");
    expect(panel.className).toContain("sm:w-80");
  });
});
