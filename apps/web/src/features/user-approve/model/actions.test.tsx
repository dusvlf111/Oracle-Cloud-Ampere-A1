import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { errorEnvelope } from "../../../../tests/mocks/handlers";
import { server } from "../../../../tests/mocks/server";

import { useUserActions } from "./actions";

const USERS = "http://localhost:3000/api/users";

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useUserActions", () => {
  it("returns true and clears pendingId on a successful action", async () => {
    server.use(
      http.post(`${USERS}/5/approve`, () =>
        HttpResponse.json({ id: 5, username: "x", role: "user", status: "active" }),
      ),
    );
    const { result } = renderHook(() => useUserActions(), { wrapper });

    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.run("approve", 5);
    });
    expect(ok).toBe(true);
    expect(result.current.error).toBeNull();
    expect(result.current.pendingId).toBeNull();
  });

  it("maps the last_admin 409 to a friendly message and returns false", async () => {
    server.use(
      http.post(`${USERS}/1/disable`, () =>
        HttpResponse.json(errorEnvelope("last_admin", "nope"), { status: 409 }),
      ),
    );
    const { result } = renderHook(() => useUserActions(), { wrapper });

    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.run("disable", 1);
    });
    expect(ok).toBe(false);
    await waitFor(() =>
      expect(result.current.error).toMatch(/last admin/),
    );
  });
});
