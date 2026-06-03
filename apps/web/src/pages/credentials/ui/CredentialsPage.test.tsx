import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { CredentialsPage } from "./CredentialsPage";

const API = "http://localhost:3000/api/credentials";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <CredentialsPage />
    </QueryClientProvider>,
  );
}

function credential(id: number, name: string) {
  return {
    id,
    name,
    tenancy_ocid: "ocid1.tenancy***",
    user_ocid: "ocid1.user***",
    fingerprint: "ab:cd:**",
    region: "ap-chuncheon-1",
    has_passphrase: false,
    created_at: "2026-06-03T10:23:45Z",
  };
}

describe("CredentialsPage", () => {
  it("lists credentials returned by the API", async () => {
    server.use(
      http.get(API, () => HttpResponse.json([credential(1, "main")])),
    );
    renderPage();
    expect(await screen.findByText("main")).toBeInTheDocument();
  });

  it("deletes a credential through the confirm dialog", async () => {
    let deleted = false;
    server.use(
      http.get(API, () =>
        HttpResponse.json(deleted ? [] : [credential(1, "main")]),
      ),
      http.delete(`${API}/1`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("main");
    await user.click(screen.getByRole("button", { name: "Delete" }));

    const dialog = await screen.findByRole("dialog", {
      name: /confirm delete credential/i,
    });
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("deleted"));
    await waitFor(() => expect(screen.queryByText("main")).not.toBeInTheDocument());
  });
});
