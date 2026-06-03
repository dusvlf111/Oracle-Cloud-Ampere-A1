"use client";

import * as React from "react";

import { Button } from "@/shared";

import { useToggleConfig } from "../model/useToggleConfig";

export interface ConfigToggleProps {
  configId: number;
  enabled: boolean;
}

/** Enable/disable button backed by an optimistic toggle mutation. */
export function ConfigToggle({ configId, enabled }: ConfigToggleProps) {
  const toggle = useToggleConfig();
  return (
    <Button
      type="button"
      aria-pressed={enabled}
      onClick={() => toggle.mutate(configId)}
      disabled={toggle.isPending}
    >
      {enabled ? "Disable" : "Enable"}
    </Button>
  );
}
