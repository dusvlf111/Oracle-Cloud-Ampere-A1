#!/usr/bin/env node
// Static validation of docker-compose.yml security invariants (task 1.7.T2).
// The live `docker compose up` + curl probe is documented in the README but
// requires a Docker daemon; this script enforces the structural guarantees
// (server NOT host-exposed, web exposes only :3000, depends_on healthy) so the
// invariant is regression-tested even without a daemon.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const text = readFileSync(resolve(root, "docker-compose.yml"), "utf8");

const errors = [];
const check = (cond, msg) => {
  if (!cond) errors.push(msg);
};

// Crude section split is enough for these invariants.
const serverBlock = text.slice(
  text.indexOf("\n  server:"),
  text.indexOf("\n  web:"),
);
const webBlock = text.slice(text.indexOf("\n  web:"));

// server must NOT publish host ports.
check(
  !/^\s*ports:/m.test(serverBlock),
  "server must NOT declare `ports:` (host exposure forbidden)",
);
check(
  /^\s*expose:/m.test(serverBlock) && /["']?8000["']?/.test(serverBlock),
  "server must `expose: 8000` for in-network access",
);
check(
  /healthcheck:/.test(serverBlock) && /healthz/.test(serverBlock),
  "server must define a /healthz healthcheck",
);

// web must publish 3000 and wait for server health.
check(/^\s*ports:/m.test(webBlock), "web must publish a host port");
check(/3000:3000/.test(webBlock), "web must publish 3000:3000");
check(
  /INTERNAL_API_URL:\s*http:\/\/server:8000/.test(webBlock),
  "web must set INTERNAL_API_URL=http://server:8000",
);
check(
  /condition:\s*service_healthy/.test(webBlock),
  "web must depend_on server: service_healthy",
);

if (errors.length) {
  console.error("docker-compose verification FAILED:");
  for (const e of errors) console.error("  - " + e);
  process.exit(1);
}
console.log("docker-compose verification OK (server not host-exposed, web :3000 only)");
