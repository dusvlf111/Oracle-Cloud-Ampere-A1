"use client";

import { useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import {
  ConfigRow,
  configsQueryKey,
  deleteConfig,
  useConfigs,
} from "@/entities/config";
import { ConfigCreateForm } from "@/features/config-create";
import { ConfigToggle } from "@/features/config-toggle";
import { Button, isApiError } from "@/shared";

export function ConfigsPage() {
  const queryClient = useQueryClient();
  const { data: configs = [], isLoading, isError } = useConfigs();

  const [toast, setToast] = React.useState<{ ok: boolean; message: string } | null>(
    null,
  );
  const [deleteTarget, setDeleteTarget] = React.useState<number | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: configsQueryKey() });

  const onConfirmDelete = async () => {
    if (deleteTarget == null) return;
    setDeleting(true);
    try {
      await deleteConfig(deleteTarget);
      setDeleteTarget(null);
      setToast({ ok: true, message: "Config deleted." });
      await invalidate();
    } catch (err) {
      setToast({
        ok: false,
        message: isApiError(err) ? err.message : "Failed to delete config.",
      });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4">
      <h1 className="text-lg font-semibold">Instance Configs</h1>

      {toast && (
        <p
          role="status"
          className={toast.ok ? "text-sm text-green-700" : "text-sm text-red-600"}
        >
          {toast.message}
        </p>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-gray-600">Add config</h2>
        <ConfigCreateForm
          onCreated={() => {
            setToast({ ok: true, message: "Config created." });
            void invalidate();
          }}
        />
      </section>

      <section className="flex flex-col gap-1">
        <h2 className="text-sm font-medium text-gray-600">Existing</h2>
        {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
        {isError && (
          <p role="alert" className="text-sm text-red-600">
            Failed to load configs.
          </p>
        )}
        {!isLoading && configs.length === 0 && (
          <p className="text-sm text-gray-500">No configs yet.</p>
        )}
        {configs.map((cfg) => (
          <ConfigRow
            key={cfg.id}
            config={cfg}
            actions={
              <>
                <ConfigToggle configId={cfg.id} enabled={cfg.enabled} />
                <Button type="button" onClick={() => setDeleteTarget(cfg.id)}>
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
          aria-label="Confirm delete config"
          className="fixed inset-0 flex items-end justify-center bg-black/40 sm:items-center"
        >
          <div className="w-full rounded-t-md bg-white p-4 shadow-lg sm:w-80 sm:rounded-md">
            <p className="text-sm">Delete this config?</p>
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
