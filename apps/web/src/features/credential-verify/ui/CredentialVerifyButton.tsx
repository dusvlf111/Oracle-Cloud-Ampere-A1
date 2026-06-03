"use client";

import * as React from "react";

import { verifyCredential } from "@/entities/credential";
import { Button, isApiError } from "@/shared";

export interface CredentialVerifyButtonProps {
  credentialId: number;
  /** Notifies the parent so it can surface a toast/status (ok + optional error). */
  onResult?: (result: { ok: boolean; error?: string }) => void;
}

/**
 * Triggers `POST /api/credentials/{id}/verify` (OCI ListAvailabilityDomains)
 * and reports the `{ ok, error? }` outcome. A failed *request* (network/401)
 * is also reported as `ok: false` so the caller can always show feedback.
 */
export function CredentialVerifyButton({
  credentialId,
  onResult,
}: CredentialVerifyButtonProps) {
  const [pending, setPending] = React.useState(false);

  const onClick = async () => {
    setPending(true);
    try {
      const res = await verifyCredential(credentialId);
      onResult?.({ ok: res.ok, error: res.error ?? undefined });
    } catch (err) {
      onResult?.({
        ok: false,
        error: isApiError(err) ? err.message : "Verification request failed",
      });
    } finally {
      setPending(false);
    }
  };

  return (
    <Button type="button" onClick={onClick} disabled={pending}>
      {pending ? "Verifying…" : "Verify"}
    </Button>
  );
}
