#!/usr/bin/env node
/**
 * sync-api.mjs — FastAPI OpenAPI → Orval 클라이언트 자동 동기화.
 *
 * 동작 순서:
 *   1. uv 가 있으면 서버 앱에서 OpenAPI 스키마를 추출해 apps/server/openapi.json 갱신
 *      (uv 가 없는 환경 — 예: web Docker 빌더 — 에서는 커밋된 스냅샷을 그대로 사용)
 *   2. 스키마가 바뀌었거나 생성물(src/shared/api)이 없으면 Orval 실행
 *
 * 사용처: 루트 `pnpm gen:api`, apps/web 의 predev/prebuild 훅.
 */
import { execSync, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SERVER_DIR = path.join(ROOT, "apps", "server");
const WEB_DIR = path.join(ROOT, "apps", "web");
const SPEC = path.join(SERVER_DIR, "openapi.json");
const STAMP = path.join(WEB_DIR, "node_modules", ".openapi-sync-hash");
const GENERATED = path.join(WEB_DIR, "src", "shared", "api", "index.ts");

const log = (msg) => console.log(`[sync-api] ${msg}`);

function hasUv() {
  return spawnSync("uv", ["--version"], { stdio: "ignore" }).status === 0;
}

// 1. OpenAPI 스키마 추출 (가능한 환경에서만)
if (hasUv()) {
  log("extracting OpenAPI schema from FastAPI app …");
  const res = spawnSync(
    "uv",
    [
      "--project", SERVER_DIR, "run", "python", "-c",
      "import json; from app.main import app; print(json.dumps(app.openapi(), sort_keys=True))",
    ],
    { cwd: SERVER_DIR, encoding: "utf-8", env: { ...process.env, PYTHONPATH: path.join(SERVER_DIR, "src") } },
  );
  if (res.status === 0 && res.stdout.trim().startsWith("{")) {
    writeFileSync(SPEC, res.stdout.trim() + "\n");
    log("openapi.json refreshed");
  } else {
    log(`WARN: schema extraction failed (exit ${res.status}); falling back to committed snapshot`);
    if (res.stderr) console.error(res.stderr.slice(-2000));
  }
} else {
  log("uv not found — using committed openapi.json snapshot");
}

if (!existsSync(SPEC)) {
  if (existsSync(GENERATED)) {
    log("no openapi.json but generated client exists — skipping");
    process.exit(0);
  }
  console.error("[sync-api] ERROR: no openapi.json and no generated client. Run with uv installed once.");
  process.exit(1);
}

// 2. 변경 감지 — 스키마 해시가 같고 생성물이 있으면 Orval 생략
const hash = createHash("sha256").update(readFileSync(SPEC)).digest("hex");
const prev = existsSync(STAMP) ? readFileSync(STAMP, "utf-8").trim() : "";
if (hash === prev && existsSync(GENERATED)) {
  log("schema unchanged — generated client is up to date");
  process.exit(0);
}

log("running orval …");
execSync("pnpm exec orval --config ./orval.config.ts", {
  cwd: WEB_DIR,
  stdio: "inherit",
  env: { ...process.env, OPENAPI_URL: path.relative(WEB_DIR, SPEC) },
});
try {
  writeFileSync(STAMP, hash + "\n");
} catch {
  /* node_modules 없는 특수 환경이면 스탬프 생략 */
}
log("done — src/shared/api regenerated");
