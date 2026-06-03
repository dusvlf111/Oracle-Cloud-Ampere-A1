"use client";

import * as React from "react";

import { testChannel } from "@/entities/channel";
import { Button, isApiError } from "@/shared";

export interface ChannelTestButtonProps {
  channelId: number;
}

/**
 * Sends a test notification via `POST /api/channels/{id}/test` and renders the
 * `{ ok, error? }` outcome inline (PRD §7.5.2).
 */
export function ChannelTestButton({ channelId }: ChannelTestButtonProps) {
  const [pending, setPending] = React.useState(false);
  const [result, setResult] = React.useState<{ ok: boolean; error?: string } | null>(
    null,
  );

  const onClick = async () => {
    setPending(true);
    setResult(null);
    try {
      const res = await testChannel(channelId);
      setResult({ ok: res.ok, error: res.error ?? undefined });
    } catch (err) {
      setResult({
        ok: false,
        error: isApiError(err) ? err.message : "Test send failed",
      });
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <Button type="button" onClick={onClick} disabled={pending}>
        {pending ? "Sending…" : "Send test"}
      </Button>
      {result && (
        <span
          role="status"
          data-testid="channel-test-result"
          className={result.ok ? "text-sm text-green-700" : "text-sm text-red-600"}
        >
          {result.ok ? "Test sent ✓" : (result.error ?? "Test failed")}
        </span>
      )}
    </div>
  );
}
