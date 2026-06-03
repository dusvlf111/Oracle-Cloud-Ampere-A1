import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { server } from "../../../../tests/mocks/server";

import { CredentialVerifyButton } from "./CredentialVerifyButton";

const VERIFY = "http://localhost:3000/api/credentials/1/verify";

describe("CredentialVerifyButton", () => {
  it("reports ok:true on a successful verify", async () => {
    server.use(http.post(VERIFY, () => HttpResponse.json({ ok: true })));
    const onResult = vi.fn();
    const user = userEvent.setup();
    render(<CredentialVerifyButton credentialId={1} onResult={onResult} />);

    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() =>
      expect(onResult).toHaveBeenCalledWith({ ok: true, error: undefined }),
    );
  });

  it("reports ok:false with the error message", async () => {
    server.use(
      http.post(VERIFY, () =>
        HttpResponse.json({ ok: false, error: "Invalid key" }),
      ),
    );
    const onResult = vi.fn();
    const user = userEvent.setup();
    render(<CredentialVerifyButton credentialId={1} onResult={onResult} />);

    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() =>
      expect(onResult).toHaveBeenCalledWith({ ok: false, error: "Invalid key" }),
    );
  });
});
