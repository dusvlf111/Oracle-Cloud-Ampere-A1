import withSerwistInit from "@serwist/next";
import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  // FSD keeps `src/app` and `src/pages` layers that are NOT Next.js routers.
  // The Next.js router lives in the root-level `app/` directory only. Restrict
  // router page detection to .tsx/.jsx so plain `index.ts` barrels in the FSD
  // layers are never treated as routes, and disable typedRoutes (its validator
  // mis-scans the FSD `src/app` layer as a second App Router root).
  pageExtensions: ["tsx", "jsx"],
  typedRoutes: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.INTERNAL_API_URL ?? "http://server:8000"}/api/:path*`,
      },
    ];
  },
};

// PWA service worker (Push 7). Source lives in the App Router at `app/sw.ts`
// and is emitted to `public/sw.js`. Disabled in development so HMR is never
// shadowed by a cached worker.
const withSerwist = withSerwistInit({
  swSrc: "app/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
});

export default withSerwist(config);
