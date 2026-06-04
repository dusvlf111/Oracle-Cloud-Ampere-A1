"use client";

import * as React from "react";

import type { User } from "@/entities/user";
import { Button } from "@/shared";

import { useUserActions } from "../model/actions";

export interface UserActionsProps {
  user: User;
}

/**
 * Per-row admin actions for a user (PRD §6.1):
 * - pending  → 승인 / 거부(확인 모달)
 * - active   → 비활성
 * - disabled → 활성
 *
 * Reject is destructive, so it routes through a confirm dialog. All actions
 * invalidate the user list on success (handled in `useUserActions`).
 */
export function UserActions({ user }: UserActionsProps) {
  const { pendingId, error, run, clearError } = useUserActions();
  const [confirmReject, setConfirmReject] = React.useState(false);
  const busy = pendingId === user.id;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {user.status === "pending" && (
        <>
          <Button
            type="button"
            className="min-h-11"
            disabled={busy}
            onClick={() => run("approve", user.id)}
          >
            {busy ? "처리 중…" : "승인"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="min-h-11"
            disabled={busy}
            onClick={() => {
              clearError();
              setConfirmReject(true);
            }}
          >
            거부
          </Button>
        </>
      )}

      {user.status === "active" && (
        <Button
          type="button"
          variant="outline"
          className="min-h-11"
          disabled={busy}
          onClick={() => run("disable", user.id)}
        >
          {busy ? "처리 중…" : "비활성"}
        </Button>
      )}

      {user.status === "disabled" && (
        <Button
          type="button"
          className="min-h-11"
          disabled={busy}
          onClick={() => run("enable", user.id)}
        >
          {busy ? "처리 중…" : "활성"}
        </Button>
      )}

      {error && (
        <p role="alert" className="basis-full text-sm text-red-600">
          {error}
        </p>
      )}

      {confirmReject && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="가입 거부 확인"
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center"
        >
          <div className="w-full rounded-t-md bg-white p-4 shadow-lg sm:w-80 sm:rounded-md">
            <p className="text-sm">
              <span className="font-semibold">{user.username}</span> 님의 가입을
              거부하시겠습니까?
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                className="min-h-11"
                disabled={busy}
                onClick={() => setConfirmReject(false)}
              >
                취소
              </Button>
              <Button
                type="button"
                className="min-h-11"
                disabled={busy}
                onClick={async () => {
                  const ok = await run("reject", user.id);
                  if (ok) setConfirmReject(false);
                }}
              >
                {busy ? "처리 중…" : "거부"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
