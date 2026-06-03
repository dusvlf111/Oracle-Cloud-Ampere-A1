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
// web block runs until the next optional profile service (postgres/redis) or EOF.
const webEnd = (() => {
  const candidates = ["\n  postgres:", "\n  redis:", "\nvolumes:"]
    .map((m) => text.indexOf(m))
    .filter((i) => i !== -1);
  return candidates.length ? Math.min(...candidates) : text.length;
})();
const webBlock = text.slice(text.indexOf("\n  web:"), webEnd);

const sliceService = (name) => {
  const start = text.indexOf(`\n  ${name}:`);
  if (start === -1) return "";
  const after = text.slice(start + 1);
  // until the next top-level (2-space) key or top-level `volumes:`.
  const m = after.search(/\n  [a-z][\w-]*:|\nvolumes:/);
  return m === -1 ? after : after.slice(0, m);
};
const postgresBlock = sliceService("postgres");
const redisBlock = sliceService("redis");

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

// server: DATABASE_URL must default to SQLite but be overridable from .env.
check(
  /DATABASE_URL:\s*\$\{DATABASE_URL:-sqlite/.test(serverBlock),
  "server DATABASE_URL must default to SQLite and be env-overridable",
);

// PostgreSQL profile service (opt-in via `--profile postgres`).
check(postgresBlock !== "", "postgres profile service must be defined");
check(
  /profiles:\s*\[?\s*["']?postgres["']?/.test(postgresBlock),
  "postgres must be gated behind the `postgres` profile",
);
check(
  /image:\s*postgres:16-alpine/.test(postgresBlock),
  "postgres must use postgres:16-alpine",
);
check(
  /healthcheck:/.test(postgresBlock) && /pg_isready/.test(postgresBlock),
  "postgres must define a pg_isready healthcheck",
);
check(
  /postgres-data:/.test(postgresBlock),
  "postgres must persist data to the postgres-data volume",
);
check(
  /^volumes:/m.test(text) && /\n {2}postgres-data:/.test(text),
  "top-level `volumes:` must declare postgres-data",
);

// Redis profile service (opt-in via `--profile redis`).
check(redisBlock !== "", "redis profile service must be defined");
check(
  /profiles:\s*\[?\s*["']?redis["']?/.test(redisBlock),
  "redis must be gated behind the `redis` profile",
);
check(
  /image:\s*redis:7-alpine/.test(redisBlock),
  "redis must use redis:7-alpine",
);
check(
  /healthcheck:/.test(redisBlock) && /redis-cli/.test(redisBlock),
  "redis must define a redis-cli ping healthcheck",
);
check(
  /REDIS_URL:\s*\$\{REDIS_URL/.test(serverBlock),
  "server must pass through REDIS_URL (empty = in-memory)",
);

if (errors.length) {
  console.error("docker-compose verification FAILED:");
  for (const e of errors) console.error("  - " + e);
  process.exit(1);
}
console.log("docker-compose verification OK (server not host-exposed, web :3000 only)");
