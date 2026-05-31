// `export const dynamic = 'error'` makes any accidental use of dynamic server
// features (e.g., Server Actions, cookies, headers) fail at build time rather
// than silently breaking the static export we ship in Phase 4.
export const dynamic = "error";

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinAlly",
  description: "AI Trading Workstation",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
