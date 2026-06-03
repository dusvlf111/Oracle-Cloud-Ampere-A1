import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { LogoutButton } from "./LogoutButton";

const LOGOUT = "http://localhost:3000/api/auth/logout";

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

describe("LogoutButton", () => {
  it("calls logout, invalidates the me query, and fires onSuccess", async () => {
    let called = false;
    server.use(
      http.post(LOGOUT, () => {
        called = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const client = new QueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<LogoutButton onSuccess={onSuccess} />, { wrapper: wrapper(client) });
    await user.click(screen.getByRole("button", { name: /sign out/i }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(called).toBe(true);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["me"] });
  });
});
