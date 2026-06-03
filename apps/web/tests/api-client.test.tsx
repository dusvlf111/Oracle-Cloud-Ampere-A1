import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import * as React from "react";
import { describe, expect, it } from "vitest";

import {
  useListCredentialsApiCredentialsGet,
  createCredentialApiCredentialsPost,
} from "@/shared/api/credentials/credentials";
import { ApiError } from "@/shared";

import { errorEnvelope } from "./mocks/handlers";
import { server } from "./mocks/server";

const API = "http://localhost:3000/api";

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("Orval-generated client (smoke)", () => {
  it("useListCredentialsApiCredentialsGet returns the MSW response", async () => {
    server.use(
      http.get(`${API}/credentials`, () =>
        HttpResponse.json([
          {
            id: 1,
            name: "main",
            tenancy_ocid: "ocid1.tenancy.oc1..aaa***",
            user_ocid: "ocid1.user.oc1..aaa***",
            fingerprint: "ab:cd:**",
            region: "ap-chuncheon-1",
            has_passphrase: true,
            created_at: "2026-06-03T10:23:45Z",
          },
        ]),
      ),
    );

    const { result } = renderHook(() => useListCredentialsApiCredentialsGet(), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].name).toBe("main");
  });

  it("parses the standard error envelope into an ApiError", async () => {
    server.use(
      http.get(`${API}/credentials`, () =>
        HttpResponse.json(errorEnvelope("unauthorized", "Session expired"), {
          status: 401,
        }),
      ),
    );

    const { result } = renderHook(() => useListCredentialsApiCredentialsGet(), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    const err = result.current.error as unknown;
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe("unauthorized");
    expect((err as ApiError).status).toBe(401);
  });

  it("sends multipart FormData for credential creation (no JSON content-type)", async () => {
    let seenContentType: string | null = null;
    server.use(
      http.post(`${API}/credentials`, ({ request }) => {
        seenContentType = request.headers.get("content-type");
        return HttpResponse.json(
          {
            id: 7,
            name: "main",
            tenancy_ocid: "ocid1.tenancy***",
            user_ocid: "ocid1.user***",
            fingerprint: "ab:cd:**",
            region: "ap-chuncheon-1",
            has_passphrase: false,
            created_at: "2026-06-03T10:23:45Z",
          },
          { status: 201 },
        );
      }),
    );

    const file = new File(["-----BEGIN KEY-----"], "key.pem", {
      type: "application/x-pem-file",
    });
    const out = await createCredentialApiCredentialsPost({
      name: "main",
      tenancy_ocid: "ocid1.tenancy",
      user_ocid: "ocid1.user",
      fingerprint: "ab:cd",
      region: "ap-chuncheon-1",
      // Orval types binary uploads as `string`; the browser/runtime accepts a
      // File/Blob just fine, so cast for the multipart request.
      private_key: file as unknown as string,
    });

    expect(out.id).toBe(7);
    // Browser-derived multipart boundary, not the bare `multipart/form-data`.
    expect(seenContentType).toContain("multipart/form-data");
    expect(seenContentType).toContain("boundary=");
  });
});
