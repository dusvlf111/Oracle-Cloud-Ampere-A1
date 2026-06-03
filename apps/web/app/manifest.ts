import type { MetadataRoute } from "next";

/**
 * PWA Web App Manifest (Push 7). Served at `/manifest.webmanifest`.
 *
 * `standalone` display makes the installed app run chromeless; the icon set
 * includes both `any` and `maskable` purposes at 192/512 so Android adaptive
 * icons render without letterboxing.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "OCI Ampere A1 Auto-Provisioner",
    short_name: "Ampere A1",
    description: "Oracle Cloud Ampere A1 자동 신청 시스템",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#0f172a",
    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/maskable-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/icons/maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
