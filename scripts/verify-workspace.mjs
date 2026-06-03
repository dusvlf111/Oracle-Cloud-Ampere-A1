#!/usr/bin/env node
// Verifies monorepo workspace configuration files exist and have the expected
// shape. Standalone (no test framework) so it can run before vitest is set up
// in task 1.6, where this logic is re-expressed as a vitest spec.
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const errors = [];

function check(cond, msg) {
  if (!cond) errors.push(msg);
}

// pnpm-workspace.yaml
const wsPath = resolve(root, "pnpm-workspace.yaml");
check(existsSync(wsPath), "pnpm-workspace.yaml missing");
if (existsSync(wsPath)) {
  const ws = readFileSync(wsPath, "utf8");
  check(/apps\/web/.test(ws), "pnpm-workspace.yaml must register apps/web");
  check(/packages\/\*/.test(ws), "pnpm-workspace.yaml must register packages/*");
}

// root package.json
const pkgPath = resolve(root, "package.json");
check(existsSync(pkgPath), "package.json missing");
if (existsSync(pkgPath)) {
  const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
  check(pkg.private === true, "root package.json must be private");
  const required = ["dev:web", "test", "test:web", "test:server", "gen:api", "lint", "build"];
  for (const s of required) {
    check(pkg.scripts && typeof pkg.scripts[s] === "string", `missing root script: ${s}`);
  }
}

// .gitignore
const giPath = resolve(root, ".gitignore");
check(existsSync(giPath), ".gitignore missing");
if (existsSync(giPath)) {
  const gi = readFileSync(giPath, "utf8");
  check(/^\.env$/m.test(gi), ".gitignore must ignore .env");
  check(/!\.env\.example/.test(gi), ".gitignore must keep .env.example");
  check(/node_modules/.test(gi), ".gitignore must ignore node_modules");
}

// .env.example
const envPath = resolve(root, ".env.example");
check(existsSync(envPath), ".env.example missing");
if (existsSync(envPath)) {
  const env = readFileSync(envPath, "utf8");
  for (const key of ["APP_SECRET", "APP_USERNAME", "APP_PASSWORD_HASH", "INTERNAL_API_URL", "CORS_ORIGINS"]) {
    check(new RegExp(`^${key}=`, "m").test(env), `.env.example must define ${key}`);
  }
}

if (errors.length) {
  console.error("workspace verification FAILED:");
  for (const e of errors) console.error("  - " + e);
  process.exit(1);
}
console.log("workspace verification OK");
