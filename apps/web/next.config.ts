import withSerwistInit from "@serwist/next";
import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  // FSD keeps `src/app` and `src/pages` layers that are NOT Next.js routers.
  // The Next.js router lives in the root-level `app/` directory only; the
  // empty root `pages/` directory pins the Pages Router root so `src/pages`
  // is never misdetected. pageExtensions must stay at its DEFAULT — narrowing
  // it to tsx/jsx silently drops `middleware.ts` (login redirect) and
  // `app/manifest.ts` (PWA manifest) from the production build (deploy bug:
  // dashboard rendered without auth redirect + manifest 404). typedRoutes
  // stays off (its validator mis-scans FSD `src/app` as a second router root).
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
