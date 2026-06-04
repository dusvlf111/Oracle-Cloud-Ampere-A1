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
  // Region is a dropdown of major regions; ap-chuncheon-1 is a preset.
  await user.selectOptions(screen.getByLabelText("Region"), "ap-chuncheon-1");
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

  it("supports a free-text region via the 직접 입력 toggle", async () => {
    server.use(
      http.post(CREATE, () => HttpResponse.json({ id: 1 }, { status: 201 })),
    );
    const onCreated = vi.fn();
    const user = userEvent.setup();
    render(<CredentialCreateForm onCreated={onCreated} />);

    await user.type(screen.getByLabelText("Name"), "main");
    await user.type(screen.getByLabelText("Tenancy OCID"), "ocid1.tenancy");
    await user.type(screen.getByLabelText("User OCID"), "ocid1.user");
    await user.type(screen.getByLabelText("Fingerprint"), "ab:cd");
    // Toggle the region field to free-text entry, then type a non-preset value.
    await user.click(
      screen.getByRole("button", { name: "직접 입력", pressed: false }),
    );
    const regionInput = screen.getByLabelText("Region") as HTMLInputElement;
    await user.type(regionInput, "il-jerusalem-1");
    expect(regionInput.value).toBe("il-jerusalem-1");
    const file = new File(["k"], "key.pem", { type: "application/x-pem-file" });
    await user.upload(screen.getByLabelText("Private key (PEM)"), file);
    await user.click(screen.getByRole("button", { name: /create credential/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalled());
  });

  it("prefills from existing and PUTs without a re-uploaded key (edit)", async () => {
    let method: string | null = null;
    let url: string | null = null;
    let hadKey = false;
    server.use(
      http.put(`${CREATE}/:id`, async ({ request }) => {
        method = request.method;
        url = request.url;
        const fd = await request.formData();
        hadKey = fd.has("private_key");
        return HttpResponse.json({ id: 3, name: "renamed" });
      }),
    );
    const onSaved = vi.fn();
    const user = userEvent.setup();
    const existing = {
      id: 3,
      name: "main",
      tenancy_ocid: "ocid1.tenancy.oc1..aaa***",
      user_ocid: "ocid1.user.oc1..aaa***",
      fingerprint: "ab:cd:**:**",
      region: "ap-seoul-1",
      has_passphrase: true,
      created_at: "2026-06-03T10:23:45Z",
    };
    render(
      <CredentialCreateForm mode="edit" initial={existing} onSaved={onSaved} />,
    );

    // Prefilled (masked) values + region preset selected.
    expect(screen.getByLabelText("Name")).toHaveValue("main");
    expect(screen.getByLabelText("Tenancy OCID")).toHaveValue(
      "ocid1.tenancy.oc1..aaa***",
    );
    expect((screen.getByLabelText("Region") as HTMLSelectElement).value).toBe(
      "ap-seoul-1",
    );

    // Save without touching the key file → no private_key part is sent.
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(method).toBe("PUT");
    expect(url).toContain("/api/credentials/3");
    expect(hadKey).toBe(false);
  });

  it("prefills a non-preset region into manual mode (edit)", () => {
    render(
      <CredentialCreateForm
        mode="edit"
        initial={{
          id: 4,
          name: "x",
          tenancy_ocid: "ocid1.tenancy***",
          user_ocid: "ocid1.user***",
          fingerprint: "ab:cd:**",
          region: "il-jerusalem-1", // not a preset
          has_passphrase: false,
          created_at: "2026-06-03T10:23:45Z",
        }}
      />,
    );
    // Region renders as a free-text input prefilled with the custom value.
    const region = screen.getByLabelText("Region") as HTMLInputElement;
    expect(region.tagName).toBe("INPUT");
    expect(region.value).toBe("il-jerusalem-1");
  });

  it("prefills fields from a pasted OCI config block (Task C)", async () => {
    const user = userEvent.setup();
    render(<CredentialCreateForm onCreated={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /구성 파일 붙여넣기/ }));
    const textarea = screen.getByLabelText("OCI config (ini)");
    const block = [
      "[DEFAULT]",
      "user=ocid1.user.oc1..aaapasted",
      "fingerprint=2a:69:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee",
      "tenancy=ocid1.tenancy.oc1..aaapasted",
      "region=ap-tokyo-1",
      "key_file=/home/me/.oci/key.pem",
    ].join("\n");
    // Paste so the ini braces/brackets aren't treated as userEvent key syntax;
    // the component's onPaste also parses immediately.
    textarea.focus();
    await user.paste(block);

    expect(screen.getByLabelText("Tenancy OCID")).toHaveValue(
      "ocid1.tenancy.oc1..aaapasted",
    );
    expect(screen.getByLabelText("User OCID")).toHaveValue(
      "ocid1.user.oc1..aaapasted",
    );
    expect(screen.getByLabelText("Fingerprint")).toHaveValue(
      "2a:69:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee",
    );
    expect((screen.getByLabelText("Region") as HTMLSelectElement).value).toBe(
      "ap-tokyo-1",
    );
    // key_file ignored → hint shown.
    expect(screen.getByText(/key_file 은 무시했습니다/)).toBeInTheDocument();
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
