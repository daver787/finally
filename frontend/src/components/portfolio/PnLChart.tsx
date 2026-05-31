"use client";

// SSR-safe wrapper around PnLChartClient. lightweight-charts touches `window`
// at module import time so we defer the import to the client via next/dynamic
// with ssr:false. Same pattern as PriceChartArea (Plan 02-02) and
// PortfolioHeatmap (this plan).
//
// This wrapper also owns the empty-state prompt — the heavyweight Lightweight
// Charts client is only mounted when there are at least 2 history points
// (the minimum a line/area series requires). The GET /api/portfolio/history
// route is not yet implemented (Phase 3 territory) so usePortfolio() returns
// [] today; this wrapper absorbs that gracefully.

import dynamic from "next/dynamic";
import type { PortfolioHistoryPoint } from "@/lib/types";

const PnLChartClient = dynamic(() => import("./PnLChartClient"), {
  ssr: false,
  loading: () => null,
});

interface PnLChartProps {
  history: PortfolioHistoryPoint[];
}

export default function PnLChart({ history }: PnLChartProps) {
  if (history.length < 2) {
    return (
      <div className="w-full h-full flex items-center justify-center text-text-muted text-sm font-mono">
        No portfolio history yet
      </div>
    );
  }

  return <PnLChartClient history={history} />;
}
