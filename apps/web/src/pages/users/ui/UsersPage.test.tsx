import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { errorEnvelope } from "../../../../tests/mocks/handlers";
import { server } from "../../../../tests/mocks/server";

import { UsersPage } from "./UsersPage";

const USERS = "http://localhost:3000/api/users";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <UsersPage />
    </QueryClientProvider>,
  );
}

function user(
  id: number,
  username: string,
  status: string,
  role = "user",
  created_at = "2026-06-01T10:00:00Z",
) {
  return { id, username, role, status, created_at, approved_at: null };
}

/** Scope queries to the desktop table so the CSS-hidden mobile cards (still in
 *  the jsdom tree) don't duplicate matches. */
function table() {
  return within(screen.getByTestId("users-table"));
}

describe("UsersPage", () => {
  it("lists users with pending sorted first", async () => {
    server.use(
      http.get(USERS, () =>
        HttpResponse.json([
          user(1, "root", "active", "admin"),
          user(2, "alice", "pending"),
        ]),
      ),
    );
    renderPage();

    await waitFor(() =>
      expect(table().getAllByTestId("user-row").length).toBe(2),
    );
    const rows = table().getAllByTestId("user-row");
    expect(within(rows[0]).getByText("alice")).toBeInTheDocument();
    expect(within(rows[1]).getByText("root")).toBeInTheDocument();
  });

  it("approves a pending user and refreshes the list", async () => {
    let approved = false;
    server.use(
      http.get(USERS, () =>
        HttpResponse.json(
          approved ? [user(2, "alice", "active")] : [user(2, "alice", "pending")],
        ),
      ),
      http.post(`${USERS}/2/approve`, () => {
        approved = true;
        return HttpResponse.json(user(2, "alice", "active"));
      }),
    );
    const u = userEvent.setup();
    renderPage();

    await waitFor(() => expect(table().getAllByTestId("user-row").length).toBe(1));
    await u.click(table().getByRole("button", { name: /^승인$/ }));

    await waitFor(() =>
      expect(table().queryByRole("button", { name: /^승인$/ })).toBeNull(),
    );
    expect(table().getByTestId("user-status-badge")).toHaveAttribute(
      "data-status",
      "active",
    );
  });

  it("rejects a pending user only after confirming in the modal", async () => {
    let rejectCalled = false;
    server.use(
      http.get(USERS, () =>
        HttpResponse.json(rejectCalled ? [] : [user(3, "bob", "pending")]),
      ),
      http.post(`${USERS}/3/reject`, () => {
        rejectCalled = true;
        return HttpResponse.json(user(3, "bob", "disabled"));
      }),
    );
    const u = userEvent.setup();
    renderPage();

    await waitFor(() => expect(table().getAllByTestId("user-row").length).toBe(1));
    await u.click(table().getByRole("button", { name: /^거부$/ }));

    // Confirm dialog appears; reject not yet sent.
    const dialog = await screen.findByRole("dialog", { name: /가입 거부 확인/ });
    expect(rejectCalled).toBe(false);
    await u.click(within(dialog).getByRole("button", { name: /^거부$/ }));

    await waitFor(() => expect(rejectCalled).toBe(true));
    await waitFor(() =>
      expect(screen.getByText(/유저가 없습니다/)).toBeInTheDocument(),
    );
  });

  it("disables an active user", async () => {
    let disabled = false;
    server.use(
      http.get(USERS, () =>
        HttpResponse.json([
          disabled ? user(4, "carol", "disabled") : user(4, "carol", "active"),
        ]),
      ),
      http.post(`${USERS}/4/disable`, () => {
        disabled = true;
        return HttpResponse.json(user(4, "carol", "disabled"));
      }),
    );
    const u = userEvent.setup();
    renderPage();

    await waitFor(() => expect(table().getAllByTestId("user-row").length).toBe(1));
    await u.click(table().getByRole("button", { name: /^비활성$/ }));

    await waitFor(() =>
      expect(table().getByRole("button", { name: /^활성$/ })).toBeInTheDocument(),
    );
  });

  it("surfaces the last_admin guard message", async () => {
    server.use(
      http.get(USERS, () =>
        HttpResponse.json([user(1, "root", "active", "admin")]),
      ),
      http.post(`${USERS}/1/disable`, () =>
        HttpResponse.json(errorEnvelope("last_admin", "cannot disable"), {
          status: 409,
        }),
      ),
    );
    const u = userEvent.setup();
    renderPage();

    await waitFor(() => expect(table().getAllByTestId("user-row").length).toBe(1));
    await u.click(table().getByRole("button", { name: /^비활성$/ }));

    expect(
      await table().findByText(/마지막 관리자는 비활성화할 수 없습니다/),
    ).toBeInTheDocument();
  });
});
