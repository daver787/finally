"use client";

// Pure-render positions table for the right-aside Portfolio panel.
//
// Six columns per row: ticker, quantity, avg cost, current price,
// unrealized P&L, % change. All numeric values pass through toFixed(2)
// so a raw float like 0.30000000000000004 never reaches the DOM. P&L and
// percent columns are color-coded by sign (green >= 0, red < 0).
//
// The component is unconditionally pure — no fetching, no state. It
// receives `positions` from PortfolioPanel (already live-priced by the
// usePortfolio() hook). When positions.length === 0 an empty-state prompt
// is rendered instead of an empty table to match the Phase 1/2 default
// (no trades executed yet → no positions).

import type { PositionEntry } from "@/lib/types";

interface PositionsTableProps {
  positions: PositionEntry[];
}

const EM_DASH = "—";

export default function PositionsTable({ positions }: PositionsTableProps) {
  if (positions.length === 0) {
    return (
      <div className="text-text-muted text-sm font-mono p-4 text-center">
        No positions yet — buy shares to populate this table
      </div>
    );
  }

  return (
    <table className="w-full text-xs font-mono">
      <thead>
        <tr className="text-text-secondary border-b border-border">
          <th className="px-2 py-1 text-left">Ticker</th>
          <th className="px-2 py-1 text-right">Qty</th>
          <th className="px-2 py-1 text-right">Avg</th>
          <th className="px-2 py-1 text-right">Last</th>
          <th className="px-2 py-1 text-right">P/L</th>
          <th className="px-2 py-1 text-right">%</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((position) => {
          const pnlColor =
            position.unrealized_pnl != null && position.unrealized_pnl < 0
              ? "text-price-down"
              : "text-price-up";
          const pctColor =
            position.pnl_percent != null && position.pnl_percent < 0
              ? "text-price-down"
              : "text-price-up";
          return (
            <tr key={position.ticker}>
              <td className="px-2 py-1 text-text-primary font-bold">
                {position.ticker}
              </td>
              <td className="px-2 py-1 text-right">
                {position.quantity.toFixed(2)}
              </td>
              <td className="px-2 py-1 text-right">
                {"$" + position.avg_cost.toFixed(2)}
              </td>
              <td className="px-2 py-1 text-right">
                {position.current_price == null
                  ? EM_DASH
                  : "$" + position.current_price.toFixed(2)}
              </td>
              <td className={`px-2 py-1 text-right ${pnlColor}`}>
                {position.unrealized_pnl == null
                  ? EM_DASH
                  : "$" + position.unrealized_pnl.toFixed(2)}
              </td>
              <td className={`px-2 py-1 text-right ${pctColor}`}>
                {position.pnl_percent == null
                  ? EM_DASH
                  : position.pnl_percent.toFixed(2) + "%"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
