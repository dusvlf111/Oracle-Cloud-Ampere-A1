// FSD VIOLATION FIXTURE (task 1.5.T1) — do not "fix".
// `entities` is a LOWER layer than `features`; importing upward must trigger
// eslint-plugin-boundaries `boundaries/element-types`. This file is excluded
// from the normal `pnpm lint` run and only linted directly by the boundaries
// verification test.
import "@/features";

export const violatesFsd = true;
