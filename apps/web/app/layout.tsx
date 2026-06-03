import type { Metadata } from "next";

import { Providers } from "@/app";
import "@/app/styles/globals.css";

export const metadata: Metadata = {
  title: "OCI Ampere A1 Auto-Provisioner",
  description: "Oracle Cloud Ampere A1 자동 신청 시스템",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
