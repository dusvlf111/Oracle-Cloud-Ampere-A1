"use client";

import { useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import {
  ChannelCard,
  channelsQueryKey,
  deleteChannel,
  useChannels,
} from "@/entities/channel";
import { ChannelCreateForm, ChannelTestButton } from "@/features/channel-test";
import { Button, isApiError } from "@/shared";

export function ChannelsPage() {
  const queryClient = useQueryClient();
  const { data: channels = [], isLoading, isError } = useChannels();

  const [toast, setToast] = React.useState<{ ok: boolean; message: string } | null>(
    null,
  );
  const [deleteTarget, setDeleteTarget] = React.useState<number | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: channelsQueryKey() });

  const onConfirmDelete = async () => {
    if (deleteTarget == null) return;
    setDeleting(true);
    try {
      await deleteChannel(deleteTarget);
      setDeleteTarget(null);
      setToast({ ok: true, message: "Channel deleted." });
      await invalidate();
    } catch (err) {
      setToast({
        ok: false,
        message: isApiError(err) ? err.message : "Failed to delete channel.",
      });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4">
      <h1 className="text-lg font-semibold">Notification Channels</h1>

      {toast && (
        <p
          role="status"
          className={toast.ok ? "text-sm text-green-700" : "text-sm text-red-600"}
        >
          {toast.message}
        </p>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-gray-600">Add channel</h2>
        <ChannelCreateForm
          onCreated={() => {
            setToast({ ok: true, message: "Channel created." });
            void invalidate();
          }}
        />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-gray-600">Existing</h2>
        {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
        {isError && (
          <p role="alert" className="text-sm text-red-600">
            Failed to load channels.
          </p>
        )}
        {!isLoading && channels.length === 0 && (
          <p className="text-sm text-gray-500">No channels yet.</p>
        )}
        {channels.map((ch) => (
          <ChannelCard
            key={ch.id}
            channel={ch}
            actions={
              <>
                <ChannelTestButton channelId={ch.id} />
                <Button type="button" onClick={() => setDeleteTarget(ch.id)}>
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
          aria-label="Confirm delete channel"
          className="fixed inset-0 flex items-center justify-center bg-black/40"
        >
          <div className="w-80 rounded-md bg-white p-4 shadow-lg">
            <p className="text-sm">Delete this channel?</p>
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
