"use client";

import { KeyRound } from "lucide-react";
import * as React from "react";

import { cn } from "@/shared";

import type { Credential } from "../model/types";

export interface CredentialCardProps {
  credential: Credential;
  /** Optional action slot (e.g. verify / delete buttons). */
  actions?: React.ReactNode;
}

function field(label: string, value: string) {
  return (
    <div className="flex justify-between gap-3 text-xs">
      <span className="text-gray-500">{label}</span>
      <span className="truncate font-mono text-gray-800" title={value}>
        {value}
      </span>
    </div>
  );
}

/**
 * Read-only credential card. The API masks `tenancy_ocid` / `user_ocid` /
 * `fingerprint` (PRD §8), so they are rendered verbatim. `has_passphrase`
 * surfaces whether an encrypted passphrase is stored.
 */
export function CredentialCard({ credential, actions }: CredentialCardProps) {
  const c = credential;
  return (
    <div
      data-testid="credential-card"
      className="flex flex-col gap-2 rounded-md border border-gray-200 p-3"
    >
      <div className="flex items-center gap-2">
        <KeyRound className="size-4 text-gray-500" aria-hidden />
        <span className="font-semibold">{c.name}</span>
        <span
          className={cn(
            "ml-auto rounded px-1.5 py-0.5 text-xs",
            c.has_passphrase
              ? "bg-amber-100 text-amber-800"
              : "bg-gray-100 text-gray-600",
          )}
        >
          {c.has_passphrase ? "passphrase" : "no passphrase"}
        </span>
      </div>
      <div className="flex flex-col gap-1">
        {field("Region", c.region)}
        {field("Tenancy", c.tenancy_ocid)}
        {field("User", c.user_ocid)}
        {field("Fingerprint", c.fingerprint)}
      </div>
      {actions && <div className="flex justify-end gap-2">{actions}</div>}
    </div>
  );
}
