import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

// In production the static export is served by FastAPI on the same origin.
// In dev we run `next dev` separately and proxy /api/* to the backend so the
// browser sees a single origin (no CORS needed on the FastAPI side).
const DEV_API_TARGET =
  process.env.NEXT_DEV_API_TARGET ?? "http://localhost:8000";

const nextConfig: NextConfig = isDev
  ? {
      async rewrites() {
        return [
          { source: "/api/:path*", destination: `${DEV_API_TARGET}/api/:path*` },
        ];
      },
    }
  : {
      output: "export",
      images: { unoptimized: true },
    };

export default nextConfig;
