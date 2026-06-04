import type { SelectOption } from "../ui/SelectField";

/** Static dropdown options for the config form's fixed-choice fields (Task A). */

export const SHAPE_OPTIONS: SelectOption[] = [
  { value: "VM.Standard.A1.Flex", label: "VM.Standard.A1.Flex" },
];

export const OCPU_OPTIONS: SelectOption[] = [1, 2, 3, 4].map((n) => ({
  value: String(n),
  label: String(n),
}));

export const MEMORY_OPTIONS: SelectOption[] = [6, 12, 18, 24].map((n) => ({
  value: String(n),
  label: `${n} GB`,
}));

export const BOOT_VOLUME_OPTIONS: SelectOption[] = [50, 100, 150, 200].map(
  (n) => ({ value: String(n), label: `${n} GB` }),
);

export const RETRY_INTERVAL_OPTIONS: SelectOption[] = [
  { value: "30", label: "30s" },
  { value: "60", label: "60s (recommended)" },
  { value: "120", label: "120s" },
  { value: "300", label: "300s" },
];

/** Empty value => unlimited (unbounded retries; sent as undefined). */
export const MAX_ATTEMPTS_OPTIONS: SelectOption[] = [
  { value: "", label: "Unlimited (default)" },
  { value: "100", label: "100" },
  { value: "500", label: "500" },
  { value: "1000", label: "1000" },
];
