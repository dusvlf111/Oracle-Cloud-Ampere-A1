import { defineConfig } from "orval";

// Generates the typed API client + React Query hooks from the FastAPI
// OpenAPI schema into src/shared/api (gitignored). Run via `pnpm gen:api`
// with the server reachable. Endpoints/tags are filled in from Push 4.
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
