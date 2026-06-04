"use client";

import * as React from "react";

import { Input, Label } from "@/shared";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  /** When true, render a "Manual input" toggle that swaps to a free-text input. */
  allowManual?: boolean;
  /** Helper hint shown below the control (e.g. Free Tier limits). */
  hint?: string;
  errorMessage?: string;
}

const SELECT_CLASS =
  // Mobile: full width, 44px tap target, 16px text (no iOS zoom). Desktop
  // tightens to the compact style used elsewhere (MetaSelectField pattern).
  "min-h-11 w-full appearance-none rounded border border-gray-300 bg-white px-3 py-2 text-base sm:min-h-0 sm:appearance-auto sm:px-2 sm:py-1 sm:text-sm";

/**
 * A static-option dropdown with an optional "Manual input" (manual entry) toggle.
 * Used for the config form's fixed-choice fields (shape, OCPU, memory, boot
 * volume, retry interval, max attempts). Mirrors {@link MetaSelectField}'s
 * mobile-friendly sizing but with a caller-supplied option list.
 */
export function SelectField({
  id,
  label,
  value,
  onChange,
  options,
  allowManual = false,
  hint,
  errorMessage,
}: SelectFieldProps) {
  const [manual, setManual] = React.useState(false);

  // A value not in the option list (e.g. an edit prefilled with a custom
  // shape) keeps the field in manual mode so it stays editable.
  const valueMissing = value !== "" && !options.some((o) => o.value === value);
  const useManual = allowManual && (manual || valueMissing);

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={id}>{label}</Label>
        {allowManual && (
          <button
            type="button"
            className="text-xs text-blue-600 underline"
            aria-pressed={useManual}
            onClick={() => setManual((m) => !m)}
          >
            {useManual ? "Choose from list" : "Manual input"}
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
          onChange={(e) => onChange(e.target.value)}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}

      {hint && <p className="text-xs text-gray-500">{hint}</p>}
      {errorMessage && (
        <p role="alert" className="text-sm text-red-600">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
