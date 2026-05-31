import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Phase 4 will serve the static export from FastAPI — keep static export on now
  // so any incompatible patterns (e.g. Server Actions) fail loudly at build time.
  output: "export",
  images: { unoptimized: true },

  // Dev-only proxy: `next dev` forwards /api/* to uvicorn on :8000 so the
  // frontend can talk to the backend over a same-origin path. Rewrites are
  // ignored under `output: 'export'` at build time — in Phase 4 the static
  // bundle is served by FastAPI directly so no proxy is needed.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
