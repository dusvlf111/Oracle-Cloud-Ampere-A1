import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { UsersRoute } from "./UsersRoute";

const ME = "http://localhost:3000/api/auth/me";
const USERS = "http://localhost:3000/api/users";

function renderRoute() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <UsersRoute />
    </QueryClientProvider>,
  );
}

describe("UsersRoute", () => {
  it("renders the users table for an admin session", async () => {
    server.use(
      http.get(ME, () =>
        HttpResponse.json({ username: "root", role: "admin", status: "active" }),
      ),
      http.get(USERS, () => HttpResponse.json([])),
    );
    renderRoute();

    expect(
      await screen.findByRole("heading", { name: /Users/ }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("users-access-denied")).toBeNull();
  });

  it("shows an access-denied notice for a non-admin session", async () => {
    server.use(
      http.get(ME, () =>
        HttpResponse.json({ username: "alice", role: "user", status: "active" }),
      ),
    );
    renderRoute();

    await waitFor(() =>
      expect(screen.getByTestId("users-access-denied")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("heading", { name: /don't have permission/i }),
    ).toBeInTheDocument();
  });
});
