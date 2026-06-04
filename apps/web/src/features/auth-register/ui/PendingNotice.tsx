"use client";

import * as React from "react";

import { Button } from "@/shared";

export interface PendingNoticeProps {
  username?: string;
  /** Back to the sign-in screen. */
  onBackToLogin?: () => void;
}

/** Shown after a non-admin signup: the account awaits admin approval (PRD §6.1). */
export function PendingNotice({ username, onBackToLogin }: PendingNoticeProps) {
  return (
    <div
      role="status"
      data-testid="pending-notice"
      className="flex flex-col gap-4 rounded-md border border-amber-200 bg-amber-50 p-4 text-center"
    >
      <h2 className="text-lg font-semibold text-amber-900">Your account is pending approval</h2>
      <p className="text-sm text-amber-800">
        {username ? `Account "${username}" ` : "Your account "}
        was created. You can sign in once an administrator approves it.
      </p>
      {onBackToLogin && (
        <Button type="button" className="min-h-11" onClick={onBackToLogin}>
          Back to sign in
        </Button>
      )}
    </div>
  );
}
