import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { useSession } from "./session";

const ME = "http://localhost:3000/api/auth/me";

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useSession", () => {
  it("parses an admin session and sets isAdmin", async () => {
    server.use(
      http.get(ME, () =>
        HttpResponse.json({ username: "root", role: "admin", status: "active" }),
      ),
    );
    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.me).toEqual({
      username: "root",
      role: "admin",
      status: "active",
    });
    expect(result.current.isAdmin).toBe(true);
  });

  it("treats a non-admin session as not admin", async () => {
    server.use(
      http.get(ME, () =>
        HttpResponse.json({ username: "alice", role: "user", status: "active" }),
      ),
    );
    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.me?.role).toBe("user");
    expect(result.current.isAdmin).toBe(false);
  });
});
