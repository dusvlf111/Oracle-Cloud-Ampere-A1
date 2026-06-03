# lint-fixtures

Intentional FSD layer-rule violations used to prove `eslint-plugin-boundaries`
is wired up correctly (task 1.5.T1).

These files live under `src/` so the boundaries elements matcher applies, but
they are NOT part of the app (excluded from tsconfig + main lint via the
dedicated check). Running:

```bash
pnpm --filter web exec eslint src/entities/__lint_fixture__/bad-import.ts
```

must FAIL with a `boundaries/element-types` error (entities → features is a
lower→upper import, which is forbidden).

The fixture source is generated at `src/entities/__lint_fixture__/` by the
verify script and asserted by `tests/lint-boundaries.test.ts`.
