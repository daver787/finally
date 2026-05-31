"use client";

// SSR-safe wrapper around PortfolioHeatmapClient. Recharts reads `window` at
// module-import time so we defer the import to the client via next/dynamic
// with ssr:false. Same pattern as PriceChartArea (Plan 02-02).
//
// This wrapper also owns the empty-state prompt so the heavyweight Treemap
// is only mounted when there are positions to display.

import dynamic from "next/dynamic";
import type { PositionEntry } from "@/lib/types";

const PortfolioHeatmapClient = dynamic(
  () => import("./PortfolioHeatmapClient"),
  { ssr: false, loading: () => null },
);

interface PortfolioHeatmapProps {
  positions: PositionEntry[];
  totalValue: number;
}

export default function PortfolioHeatmap({
  positions,
  totalValue,
}: PortfolioHeatmapProps) {
  if (positions.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center text-text-muted text-sm font-mono">
        No positions yet
      </div>
    );
  }

  return (
    <PortfolioHeatmapClient positions={positions} totalValue={totalValue} />
  );
}
