#!/usr/bin/env node
// Static validation of docker-compose security invariants (task 1.7.T2 / 8.5).
// The live `docker compose up` + curl probe is documented in the README but
// requires a Docker daemon; this script enforces the structural guarantees
// (server NOT host-exposed, web exposes only :3000, depends_on healthy) so the
// invariant is regression-tested even without a daemon.
//
// Two compose modes:
//   simple — docker-compose.yml            (SQLite + in-memory rate limit)
//   full   — + docker-compose.full.yml     (PostgreSQL + Redis override)
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const text = readFileSync(resolve(root, "docker-compose.yml"), "utf8");
const fullText = readFileSync(resolve(root, "docker-compose.full.yml"), "utf8");

const errors = [];
const check = (cond, msg) => {
  if (!cond) errors.push(msg);
};

const sliceService = (src, name) => {
  const start = src.indexOf(`\n  ${name}:`);
  if (start === -1) return "";
  const after = src.slice(start + 1);
  // until the next top-level (2-space) key or top-level `volumes:`.
  const m = after.search(/\n  [a-z][\w-]*:|\nvolumes:/);
  return m === -1 ? after : after.slice(0, m);
};

// ---------------------------------------------------------------- simple ---
const serverBlock = sliceService(text, "server");
const webBlock = sliceService(text, "web");

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
check(
  /REDIS_URL:\s*\$\{REDIS_URL/.test(serverBlock),
  "server must pass through REDIS_URL (empty = in-memory)",
);

// simple mode must NOT bundle postgres/redis (they live in the full override).
check(
  sliceService(text, "postgres") === "" && sliceService(text, "redis") === "",
  "base compose must not define postgres/redis (full override owns them)",
);

// ------------------------------------------------------------------ full ---
const fullServer = sliceService(fullText, "server");
const postgresBlock = sliceService(fullText, "postgres");
const redisBlock = sliceService(fullText, "redis");

check(postgresBlock !== "", "full: postgres service must be defined");
check(
  /image:\s*postgres:16-alpine/.test(postgresBlock),
  "full: postgres must use postgres:16-alpine",
);
check(
  !/^\s*ports:/m.test(postgresBlock),
  "full: postgres must NOT publish host ports (internal network only)",
);
check(
  /healthcheck:/.test(postgresBlock) && /pg_isready/.test(postgresBlock),
  "full: postgres must define a pg_isready healthcheck",
);
check(
  /postgres-data:/.test(postgresBlock),
  "full: postgres must persist data to the postgres-data volume",
);
check(
  /^volumes:/m.test(fullText) && /\n {2}postgres-data:/.test(fullText),
  "full: top-level `volumes:` must declare postgres-data",
);

check(redisBlock !== "", "full: redis service must be defined");
check(
  /image:\s*redis:7-alpine/.test(redisBlock),
  "full: redis must use redis:7-alpine",
);
check(
  !/^\s*ports:/m.test(redisBlock),
  "full: redis must NOT publish host ports (internal network only)",
);
check(
  /healthcheck:/.test(redisBlock) && /redis-cli/.test(redisBlock),
  "full: redis must define a redis-cli ping healthcheck",
);

// full: server must be wired to postgres/redis and wait for their health.
check(
  /DATABASE_URL:\s*\$\{DATABASE_URL:-postgresql\+psycopg/.test(fullServer),
  "full: server DATABASE_URL must default to the bundled postgres",
);
check(
  /REDIS_URL:\s*\$\{REDIS_URL:-redis:\/\/redis:6379/.test(fullServer),
  "full: server REDIS_URL must default to the bundled redis",
);
check(
  /postgres:\s*\n\s*condition:\s*service_healthy/.test(fullServer) &&
    /redis:\s*\n\s*condition:\s*service_healthy/.test(fullServer),
  "full: server must depend_on postgres+redis service_healthy",
);

if (errors.length) {
  console.error("docker-compose verification FAILED:");
  for (const e of errors) console.error("  - " + e);
  process.exit(1);
}
console.log(
  "docker-compose verification OK (simple: SQLite, full: +postgres/redis, server never host-exposed)",
);
