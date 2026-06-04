import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { PollingStatus } from "./PollingStatus";

const API = "http://localhost:3000/api/status/polling";

function item(over: Record<string, unknown> = {}) {
  return {
    config_id: 1,
    config_name: "prod-a1",
    credential_name: "main-account",
    shape: "VM.Standard.A1.Flex",
    ocpus: 4,
    memory_gb: 24,
    retry_interval_sec: 60,
    last_attempt_status: "out_of_capacity",
    last_attempt_at: "2026-06-04T11:59:30Z",
    total_attempts: 12,
    ...over,
  };
}

function renderWidget() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <PollingStatus />
    </QueryClientProvider>,
  );
}

describe("PollingStatus", () => {
  it("renders config + credential names, spec and attempt summary", async () => {
    server.use(
      http.get(API, () =>
        HttpResponse.json([
          item({
            config_id: 1,
            config_name: "prod-a1",
            credential_name: "main-account",
            total_attempts: 12,
            last_attempt_status: "out_of_capacity",
          }),
        ]),
      ),
    );
    renderWidget();

    const card = await screen.findByTestId("polling-card");
    expect(within(card).getByText("prod-a1")).toBeInTheDocument();
    expect(within(card).getByText("main-account")).toBeInTheDocument();
    expect(within(card).getByText("VM.Standard.A1.Flex")).toBeInTheDocument();
    expect(within(card).getByText("4 OCPU / 24 GB")).toBeInTheDocument();
    expect(within(card).getByTestId("attempt-status-badge")).toHaveTextContent(
      "out of capacity",
    );
    expect(within(card).getByText(/12/)).toBeInTheDocument();
  });

  it("shows the credential dash fallback when credential_name is null", async () => {
    server.use(
      http.get(API, () =>
        HttpResponse.json([item({ credential_name: null })]),
      ),
    );
    renderWidget();

    const card = await screen.findByTestId("polling-card");
    expect(within(card).getByText("Account")).toBeInTheDocument();
    expect(within(card).getByText("—")).toBeInTheDocument();
  });

  it("shows 'No attempts yet' when there are no attempts yet", async () => {
    server.use(
      http.get(API, () =>
        HttpResponse.json([
          item({ total_attempts: 0, last_attempt_status: null, last_attempt_at: null }),
        ]),
      ),
    );
    renderWidget();

    const card = await screen.findByTestId("polling-card");
    expect(within(card).getByText("No attempts yet")).toBeInTheDocument();
    expect(within(card).queryByTestId("attempt-status-badge")).toBeNull();
  });

  it("shows the empty state when nothing is being polled", async () => {
    server.use(http.get(API, () => HttpResponse.json([])));
    renderWidget();

    await waitFor(() =>
      expect(screen.getByTestId("polling-empty")).toHaveTextContent(
        "No active configs.",
      ),
    );
    expect(screen.queryByTestId("polling-card")).toBeNull();
  });
});
