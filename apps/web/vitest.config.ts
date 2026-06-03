import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const r = (p: string) => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    environmentOptions: {
      jsdom: { url: "http://localhost:3000" },
    },
    setupFiles: ["./tests/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "tests/**/*.test.{ts,tsx}"],
    exclude: ["node_modules", ".next", "src/**/__lint_fixture__/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "text-summary"],
    },
  },
  resolve: {
    alias: {
      "@/app": r("./src/app"),
      "@/pages": r("./src/pages"),
      "@/widgets": r("./src/widgets"),
      "@/features": r("./src/features"),
      "@/entities": r("./src/entities"),
      "@/shared": r("./src/shared"),
    },
  },
});
