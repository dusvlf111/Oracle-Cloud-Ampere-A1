"use client";

import { useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import {
  CredentialCard,
  credentialsQueryKey,
  deleteCredential,
  useCredentials,
} from "@/entities/credential";
import {
  CredentialCreateForm,
  CredentialVerifyButton,
} from "@/features/credential-verify";
import { Button, isApiError } from "@/shared";

interface Toast {
  ok: boolean;
  message: string;
}

export function CredentialsPage() {
  const queryClient = useQueryClient();
  const { data: credentials = [], isLoading, isError } = useCredentials();

  const [toast, setToast] = React.useState<Toast | null>(null);
  const [deleteTarget, setDeleteTarget] = React.useState<number | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: credentialsQueryKey() });

  const onVerifyResult = (r: { ok: boolean; error?: string }) =>
    setToast({
      ok: r.ok,
      message: r.ok
        ? "Credential verified successfully."
        : (r.error ?? "Verification failed."),
    });

  const onConfirmDelete = async () => {
    if (deleteTarget == null) return;
    setDeleting(true);
    try {
      await deleteCredential(deleteTarget);
      setDeleteTarget(null);
      setToast({ ok: true, message: "Credential deleted." });
      await invalidate();
    } catch (err) {
      setToast({
        ok: false,
        message: isApiError(err) ? err.message : "Failed to delete credential.",
      });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4">
      <h1 className="text-lg font-semibold">OCI Credentials</h1>

      {toast && (
        <p
          role="status"
          className={
            toast.ok ? "text-sm text-green-700" : "text-sm text-red-600"
          }
        >
          {toast.message}
        </p>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-gray-600">Add credential</h2>
        <CredentialCreateForm
          onCreated={() => {
            setToast({ ok: true, message: "Credential created." });
            void invalidate();
          }}
        />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-gray-600">Existing</h2>
        {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
        {isError && (
          <p role="alert" className="text-sm text-red-600">
            Failed to load credentials.
          </p>
        )}
        {!isLoading && credentials.length === 0 && (
          <p className="text-sm text-gray-500">No credentials yet.</p>
        )}
        {credentials.map((c) => (
          <CredentialCard
            key={c.id}
            credential={c}
            actions={
              <>
                <CredentialVerifyButton
                  credentialId={c.id}
                  onResult={onVerifyResult}
                />
                <Button type="button" onClick={() => setDeleteTarget(c.id)}>
                  Delete
                </Button>
              </>
            }
          />
        ))}
      </section>

      {deleteTarget != null && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Confirm delete credential"
          className="fixed inset-0 flex items-center justify-center bg-black/40"
        >
          <div className="w-80 rounded-md bg-white p-4 shadow-lg">
            <p className="text-sm">Delete this credential? This cannot be undone.</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="button"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
              >
                Cancel
              </Button>
              <Button type="button" onClick={onConfirmDelete} disabled={deleting}>
                {deleting ? "Deleting…" : "Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
