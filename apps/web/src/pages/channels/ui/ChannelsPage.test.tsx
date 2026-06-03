import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { ChannelsPage } from "./ChannelsPage";

const API = "http://localhost:3000/api/channels";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ChannelsPage />
    </QueryClientProvider>,
  );
}

function channel(id: number, name: string) {
  return {
    id,
    name,
    type: "ntfy",
    enabled: true,
    config: { server_url: "https://ntfy.supabin.com", topic: "alerts" },
    created_at: "2026-06-03T10:24:00Z",
    updated_at: "2026-06-03T10:24:00Z",
  };
}

describe("ChannelsPage", () => {
  it("lists channels and runs a test send", async () => {
    server.use(
      http.get(API, () => HttpResponse.json([channel(2, "supabin ntfy")])),
      http.post(`${API}/2/test`, () => HttpResponse.json({ ok: true })),
    );
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("supabin ntfy");
    await user.click(screen.getByRole("button", { name: /send test/i }));
    expect(await screen.findByTestId("channel-test-result")).toHaveTextContent(
      /test sent/i,
    );
  });

  it("deletes a channel via the confirm dialog", async () => {
    let deleted = false;
    server.use(
      http.get(API, () =>
        HttpResponse.json(deleted ? [] : [channel(2, "supabin ntfy")]),
      ),
      http.delete(`${API}/2`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("supabin ntfy");
    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", {
      name: /confirm delete channel/i,
    });
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("deleted"),
    );
    await waitFor(() =>
      expect(screen.queryByText("supabin ntfy")).not.toBeInTheDocument(),
    );
  });

  it("renders the confirm dialog as a mobile bottom sheet (responsive)", async () => {
    server.use(http.get(API, () => HttpResponse.json([channel(2, "supabin ntfy")])));
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("supabin ntfy");
    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", { name: /confirm delete channel/i });
    const panel = dialog.querySelector("div")!;
    expect(panel.className).toContain("w-full");
    expect(panel.className).toContain("sm:w-80");
  });
});
