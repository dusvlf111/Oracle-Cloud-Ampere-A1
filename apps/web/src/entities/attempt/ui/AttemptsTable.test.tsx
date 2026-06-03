import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { AttemptsTable } from "./AttemptsTable";

const API = "http://localhost:3000/api/attempts";

function attempt(over: Record<string, unknown> = {}) {
  return {
    id: 1,
    config_id: 5,
    attempted_at: "2026-06-03T10:30:11Z",
    status: "out_of_capacity",
    message: "Out of host capacity",
    instance_ocid: null,
    duration_ms: 1234,
    ...over,
  };
}

function renderTable() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AttemptsTable />
    </QueryClientProvider>,
  );
}

describe("AttemptsTable", () => {
  it("renders rows with status badge and duration", async () => {
    server.use(
      http.get(API, () =>
        HttpResponse.json([
          attempt({ id: 1, status: "success", instance_ocid: "ocid1.instance..ok", duration_ms: 2200 }),
          attempt({ id: 2, status: "out_of_capacity", duration_ms: 800 }),
        ]),
      ),
    );
    renderTable();

    await waitFor(() => expect(screen.getAllByTestId("attempt-row")).toHaveLength(2));
    // Scope assertions to the table rows (the mobile card list mirrors them).
    const rows = screen.getAllByTestId("attempt-row");
    expect(within(rows[0]).getByTestId("attempt-status-badge")).toHaveTextContent("success");
    expect(within(rows[1]).getByTestId("attempt-status-badge")).toHaveTextContent(
      "out of capacity",
    );
    expect(within(rows[0]).getByText("2.2 s")).toBeInTheDocument();
    expect(within(rows[1]).getByText("800 ms")).toBeInTheDocument();
    expect(within(rows[0]).getByText("ocid1.instance..ok")).toBeInTheDocument();
  });

  it("renders both the desktop table and the mobile card list from the same data", async () => {
    server.use(
      http.get(API, () =>
        HttpResponse.json([
          attempt({ id: 1, status: "success", instance_ocid: "ocid1.instance..ok" }),
          attempt({ id: 2, status: "rate_limited" }),
        ]),
      ),
    );
    renderTable();

    await waitFor(() => expect(screen.getAllByTestId("attempt-row")).toHaveLength(2));
    // Mobile card presentation lives in the same slice and mirrors the rows.
    expect(screen.getByTestId("attempt-card-list")).toBeInTheDocument();
    expect(screen.getAllByTestId("attempt-card")).toHaveLength(2);
  });

  it("sends config_id and status as query params when filtered", async () => {
    const seen: Array<Record<string, string | null>> = [];
    server.use(
      http.get(API, ({ request }) => {
        const url = new URL(request.url);
        seen.push({
          config_id: url.searchParams.get("config_id"),
          status: url.searchParams.get("status"),
        });
        return HttpResponse.json([]);
      }),
    );
    const user = userEvent.setup();
    renderTable();

    await waitFor(() => expect(seen.length).toBeGreaterThan(0));

    await user.type(screen.getByLabelText("Filter by config id"), "7");
    await user.selectOptions(screen.getByLabelText("Filter by status"), "rate_limited");

    await waitFor(() => {
      const last = seen[seen.length - 1];
      expect(last.config_id).toBe("7");
      expect(last.status).toBe("rate_limited");
    });
  });
});
