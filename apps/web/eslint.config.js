import js from "@eslint/js";
import boundaries from "eslint-plugin-boundaries";
import tseslint from "typescript-eslint";

/**
 * FSD layer rules enforced via eslint-plugin-boundaries (PRD §5):
 *   app > pages > widgets > features > entities > shared
 * - upper layers may import lower layers
 * - lower layers may NOT import upper layers
 * - same-layer cross-slice imports are disallowed (go through shared)
 */
export default tseslint.config(
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "next-env.d.ts",
      "src/shared/api/**", // Orval-generated
      "src/**/__lint_fixture__/**", // intentional FSD-violation fixtures (1.5.T1)
      "public/sw.js", // Serwist-generated service worker (build artifact)
      "public/swe-worker-*.js", // Serwist runtime worker (build artifact)
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx,js,jsx}"],
    plugins: { boundaries },
    settings: {
      "import/resolver": {
        typescript: { project: "./tsconfig.json" },
        node: true,
      },
      "boundaries/include": ["src/**/*"],
      // `mode: folder` + a pattern that matches the layer directory itself so
      // both the layer barrel (`src/<layer>/index.ts`) and individual slices
      // (`src/<layer>/<slice>/...`) classify to the same layer type.
      "boundaries/elements": [
        { type: "app", pattern: "src/app", mode: "folder" },
        { type: "pages", pattern: "src/pages", mode: "folder" },
        { type: "widgets", pattern: "src/widgets", mode: "folder" },
        { type: "features", pattern: "src/features", mode: "folder" },
        { type: "entities", pattern: "src/entities", mode: "folder" },
        { type: "shared", pattern: "src/shared", mode: "folder" },
      ],
    },
    rules: {
      "boundaries/element-types": [
        "error",
        {
          default: "disallow",
          rules: [
            { from: "app", allow: ["pages", "widgets", "features", "entities", "shared"] },
            { from: "pages", allow: ["widgets", "features", "entities", "shared"] },
            { from: "widgets", allow: ["features", "entities", "shared"] },
            { from: "features", allow: ["entities", "shared"] },
            { from: "entities", allow: ["shared"] },
            { from: "shared", allow: ["shared"] },
          ],
        },
      ],
    },
  },
  {
    // Test files: relax rules that fight with vitest globals / assertions.
    files: ["**/*.test.{ts,tsx}", "tests/**/*"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
);
