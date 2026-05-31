"use client";

// SSR-safe wrapper around the heavy PriceChart component.
// lightweight-charts reads `window` at module-import time, so a direct import
// crashes `next build` under output: 'export'. next/dynamic with ssr:false
// defers the import to the client at runtime.
// This wrapper also owns the empty/loading prompts — the heavyweight chart
// is only mounted once a ticker is selected AND at least 2 sparkline points
// exist, keeping the initial paint cheap and SSR-pristine.

import dynamic from "next/dynamic";
import { useStore } from "@/store";

const PriceChart = dynamic(() => import("./PriceChart"), {
  ssr: false,
  loading: () => null,
});

export default function PriceChartArea() {
  const selectedTicker = useStore((s) => s.selectedTicker);
  const hasEnoughData = useStore(
    (s) =>
      s.selectedTicker !== null &&
      (s.sparklines[s.selectedTicker]?.length ?? 0) >= 2,
  );

  return (
    <div className="flex items-center justify-center text-text-muted text-sm border border-border m-2 rounded overflow-hidden h-full w-full relative bg-bg-base">
      {selectedTicker === null ? (
        <span className="text-text-muted text-sm font-mono">
          Select a ticker to view the chart
        </span>
      ) : !hasEnoughData ? (
        <div className="flex flex-col items-center gap-1">
          <span className="text-text-primary font-mono font-bold text-base">
            {selectedTicker}
          </span>
          <span className="text-text-muted text-sm font-mono">
            Waiting for price data...
          </span>
        </div>
      ) : (
        <>
          <span className="absolute top-2 left-3 z-10 text-text-primary font-mono font-bold text-sm pointer-events-none">
            {selectedTicker}
          </span>
          <PriceChart />
        </>
      )}
    </div>
  );
}
