"use client";

import * as React from "react";

import { Input, Label } from "@/shared";

export interface MetaOption {
  value: string;
  label: string;
}

export interface MetaSelectFieldProps {
  id: string;
  label: string;
  /** Current field value (OCID / AD name). */
  value: string;
  onChange: (value: string) => void;
  options: MetaOption[];
  /** Lookup running (credential selected, request in flight). */
  isLoading: boolean;
  /** Lookup failed (e.g. 502) — surface message + force manual input. */
  isError: boolean;
  /** No credential selected yet → dropdown disabled, hint shown. */
  hasCredential: boolean;
  /** Validation error message for the field. */
  errorMessage?: string;
}

const SELECT_CLASS =
  // Mobile: full width, 44px tap target, 16px text (no iOS zoom). Desktop
  // tightens to the compact table style (AttemptsTable pattern).
  "min-h-11 w-full appearance-none rounded border border-gray-300 bg-white px-3 py-2 text-base sm:min-h-0 sm:appearance-auto sm:px-2 sm:py-1 sm:text-sm";

/**
 * A meta-driven field that renders a dropdown of OCI-fetched options with a
 * "직접 입력" (manual entry) fallback. The manual toggle is auto-enabled when the
 * lookup fails so a different-compartment / 502 case never blocks the user.
 */
export function MetaSelectField({
  id,
  label,
  value,
  onChange,
  options,
  isLoading,
  isError,
  hasCredential,
  errorMessage,
}: MetaSelectFieldProps) {
  const [manual, setManual] = React.useState(false);

  // A failed lookup forces manual mode (PRD: auto fallback to manual input).
  React.useEffect(() => {
    if (isError) setManual(true);
  }, [isError]);

  // The selected value is not in the fetched options (e.g. another
  // compartment) → keep the user in manual mode so it stays editable.
  const valueMissing =
    value !== "" && !options.some((o) => o.value === value);
  const useManual = manual || isError || valueMissing || !hasCredential;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={id}>{label}</Label>
        {hasCredential && !isError && (
          <button
            type="button"
            className="text-xs text-blue-600 underline"
            aria-pressed={useManual}
            onClick={() => setManual((m) => !m)}
          >
            {useManual ? "목록에서 선택" : "직접 입력"}
          </button>
        )}
      </div>

      {useManual ? (
        <Input
          id={id}
          aria-label={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <select
          id={id}
          aria-label={label}
          className={SELECT_CLASS}
          value={value}
          disabled={isLoading || options.length === 0}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">
            {isLoading ? "불러오는 중…" : `${label} 선택…`}
          </option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}

      {!hasCredential && (
        <p className="text-xs text-gray-500">
          먼저 자격증명을 선택하세요.
        </p>
      )}
      {isError && (
        <p role="status" className="text-xs text-amber-600">
          OCI 조회 실패 — 직접 입력으로 전환했습니다.
        </p>
      )}
      {errorMessage && (
        <p role="alert" className="text-sm text-red-600">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
