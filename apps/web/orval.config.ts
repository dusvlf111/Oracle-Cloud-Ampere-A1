import { defineConfig } from "orval";

// Generates the typed API client + React Query hooks from the FastAPI
// OpenAPI schema into src/shared/api (gitignored). Run via `pnpm gen:api`.
//
// `input` accepts a URL or a local file path. Two ways to provide the spec:
//   1. Live server:  OPENAPI_URL=http://localhost:8000/openapi.json pnpm gen:api
//   2. Static file:  (from apps/server)
//        uv run python -c "import json; from app.main import app; \
//          print(json.dumps(app.openapi()))" > openapi.json
//      then          OPENAPI_URL=../server/openapi.json pnpm gen:api
//
// The generated client uses the `httpClient` mutator (src/shared/http) so every
// hook shares cookie auth, the `/api` base and the standard error envelope.
export default defineConfig({
  api: {
    input: process.env.OPENAPI_URL ?? "http://localhost:8000/openapi.json",
    output: {
      mode: "tags-split",
      target: "src/shared/api/index.ts",
      schemas: "src/shared/api/schemas",
      client: "react-query",
      override: {
        mutator: {
          path: "src/shared/http/client.ts",
          name: "httpClient",
        },
      },
    },
  },
});
