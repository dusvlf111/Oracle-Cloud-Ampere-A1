import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { CredentialCreateForm } from "./CredentialCreateForm";

const CREATE = "http://localhost:3000/api/credentials";

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Name"), "main");
  await user.type(screen.getByLabelText("Tenancy OCID"), "ocid1.tenancy");
  await user.type(screen.getByLabelText("User OCID"), "ocid1.user");
  await user.type(screen.getByLabelText("Fingerprint"), "ab:cd");
  await user.type(screen.getByLabelText("Region"), "ap-chuncheon-1");
  const file = new File(["-----BEGIN KEY-----"], "key.pem", {
    type: "application/x-pem-file",
  });
  await user.upload(screen.getByLabelText("Private key (PEM)"), file);
}

describe("CredentialCreateForm", () => {
  it("submits a multipart FormData body and calls onCreated", async () => {
    let contentType: string | null = null;
    server.use(
      http.post(CREATE, ({ request }) => {
        contentType = request.headers.get("content-type");
        return HttpResponse.json(
          {
            id: 9,
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
    const onCreated = vi.fn();
    const user = userEvent.setup();
    render(<CredentialCreateForm onCreated={onCreated} />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /create credential/i }));

    await waitFor(() =>
      expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: 9 })),
    );
    expect(contentType).toContain("multipart/form-data");
    expect(contentType).toContain("boundary=");
  });

  it("blocks submit and shows validation errors when required fields are empty", async () => {
    // No MSW handler — if a request fired, onUnhandledRequest:'error' fails.
    const onCreated = vi.fn();
    const user = userEvent.setup();
    render(<CredentialCreateForm onCreated={onCreated} />);

    await user.click(screen.getByRole("button", { name: /create credential/i }));

    expect(await screen.findByText("Name is required")).toBeInTheDocument();
    expect(screen.getByText("Private key file is required")).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
  });
});
