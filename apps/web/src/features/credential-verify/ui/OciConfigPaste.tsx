"use client";

import * as React from "react";

import { Button, Label } from "@/shared";

import { parseOciConfig, type ParsedOciConfig } from "../lib/parseOciConfig";

export interface OciConfigPasteProps {
  /** Called with the parsed fields when the user applies a pasted config. */
  onParsed: (fields: ParsedOciConfig) => void;
}

const TEXTAREA_CLASS =
  "min-h-28 w-full rounded border border-gray-300 bg-white px-3 py-2 font-mono text-base sm:text-sm";

/**
 * Collapsible "📋 구성 파일 붙여넣기" area (Task C). The user pastes the ini
 * block Oracle's console shows; on apply (or paste) we parse it and prefill the
 * credential form's OCID / fingerprint / region fields. The key_file line is
 * ignored with a hint that the PEM is uploaded below.
 */
export function OciConfigPaste({ onParsed }: OciConfigPasteProps) {
  const [open, setOpen] = React.useState(false);
  const [text, setText] = React.useState("");
  const [status, setStatus] = React.useState<string | null>(null);

  const apply = React.useCallback(
    (value: string) => {
      const { fields, matchedKeys, keyFileIgnored } = parseOciConfig(value);
      if (matchedKeys.length === 0) {
        setStatus("인식된 항목이 없습니다. ini 형식을 확인하세요.");
        return;
      }
      onParsed(fields);
      const keyNote = keyFileIgnored
        ? " key_file 은 무시했습니다 — 키 파일은 아래에서 업로드하세요."
        : "";
      setStatus(`${matchedKeys.length}개 항목을 채웠습니다.${keyNote}`);
    },
    [onParsed],
  );

  return (
    <div className="rounded border border-dashed border-gray-300 p-3">
      <button
        type="button"
        className="flex w-full items-center justify-between text-sm font-medium"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <span>📋 구성 파일 붙여넣기</span>
        <span aria-hidden className="text-gray-500">
          {open ? "▲" : "▼"}
        </span>
      </button>

      {open && (
        <div className="mt-3 flex flex-col gap-2">
          <Label htmlFor="oci-config-paste">OCI config (ini)</Label>
          <textarea
            id="oci-config-paste"
            aria-label="OCI config (ini)"
            className={TEXTAREA_CLASS}
            placeholder={
              "[DEFAULT]\nuser=ocid1.user.oc1..aaa...\nfingerprint=2a:69:...\ntenancy=ocid1.tenancy.oc1..aaa...\nregion=ap-chuncheon-1"
            }
            value={text}
            onChange={(e) => setText(e.target.value)}
            onPaste={(e) => {
              // Parse the pasted content directly (state hasn't updated yet).
              const pasted = e.clipboardData.getData("text");
              if (pasted) {
                setText(pasted);
                apply(pasted);
                e.preventDefault();
              }
            }}
          />
          <div className="flex items-center gap-2">
            <Button type="button" onClick={() => apply(text)}>
              자동 채우기
            </Button>
            <span className="text-xs text-gray-500">
              키 파일은 아래에서 업로드하세요.
            </span>
          </div>
          {status && (
            <p role="status" className="text-xs text-blue-700">
              {status}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
