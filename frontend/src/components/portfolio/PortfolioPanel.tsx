"use client";

// Thin orchestration component for the right-aside Portfolio surface.
// Calls usePortfolio() exactly once (which owns fetching, 10s polling, and
// live-price enrichment of positions from useStore.prices) and renders three
// stacked sections inside a CSS-Grid column: heatmap (allocation), P&L area
// chart (portfolio value), and positions table. Each section owns its own
// empty-state prompt so the Phase 1/2 default (zero trades, zero history)
// renders gracefully — no broken charts, no console warnings.

import { useStore } from "@/store";
import { usePortfolio } from "@/hooks/usePortfolio";
import PortfolioHeatmap from "./PortfolioHeatmap";
import PnLChart from "./PnLChart";
import PositionsTable from "./PositionsTable";

export default function PortfolioPanel() {
  const { portfolio, positions, history } = usePortfolio();
  // Prefer the live-priced server total_value; fall back to the store's
  // header slice when /api/portfolio has not yet resolved on mount.
  // getState() reads once per render and avoids subscribing PortfolioPanel
  // to the legacy totalValue slice (Header already owns that subscription).
  const totalValue = portfolio?.total_value ?? useStore.getState().totalValue;

  return (
    <div className="h-full grid grid-rows-[2fr_1fr_3fr] border-l border-border bg-bg-base overflow-hidden">
      <section className="grid grid-rows-[auto_1fr] overflow-hidden">
        <h2 className="text-text-secondary text-xs font-mono uppercase tracking-wide px-3 py-2 border-b border-border">
          Allocation
        </h2>
        <div className="p-2 h-full overflow-hidden">
          <PortfolioHeatmap positions={positions} totalValue={totalValue} />
        </div>
      </section>
      <section className="grid grid-rows-[auto_1fr] overflow-hidden">
        <h2 className="text-text-secondary text-xs font-mono uppercase tracking-wide px-3 py-2 border-b border-border">
          Portfolio Value
        </h2>
        <div className="p-2 h-full overflow-hidden">
          <PnLChart history={history} />
        </div>
      </section>
      <section className="grid grid-rows-[auto_1fr] overflow-hidden">
        <h2 className="text-text-secondary text-xs font-mono uppercase tracking-wide px-3 py-2 border-b border-border">
          Positions
        </h2>
        <div className="overflow-y-auto h-full">
          <PositionsTable positions={positions} />
        </div>
      </section>
    </div>
  );
}
