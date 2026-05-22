"use client";

// PositionsTable — all holdings with live P&L recomputed from SSE prices.

import type { Position } from "@/lib/types";
import { fmtMoney, fmtPct, fmtPrice, fmtQty } from "@/lib/format";

interface PositionsTableProps {
  positions: Position[];
  getLivePrice: (ticker: string) => number | undefined;
  onSelect: (ticker: string) => void;
  selected: string | null;
}

export function PositionsTable({
  positions,
  getLivePrice,
  onSelect,
  selected,
}: PositionsTableProps) {
  const held = positions.filter((p) => p.quantity > 0);

  return (
    <div className="panel panel-in flex flex-col h-full overflow-hidden">
      <div className="panel-header">
        <span className="panel-title">Positions</span>
        <span className="text-[10px] tnum" style={{ color: "var(--ink-faint)" }}>
          {held.length} OPEN
        </span>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full text-xs">
          <thead>
            <tr
              className="text-[9px] font-bold tracking-[0.1em] uppercase"
              style={{ color: "var(--ink-faint)" }}
            >
              <th className="text-left px-3 py-1.5 sticky top-0" style={headStyle}>
                Ticker
              </th>
              <th className="text-right px-3 py-1.5 sticky top-0" style={headStyle}>
                Qty
              </th>
              <th className="text-right px-3 py-1.5 sticky top-0" style={headStyle}>
                Avg Cost
              </th>
              <th className="text-right px-3 py-1.5 sticky top-0" style={headStyle}>
                Last
              </th>
              <th className="text-right px-3 py-1.5 sticky top-0" style={headStyle}>
                Unreal. P&L
              </th>
              <th className="text-right px-3 py-1.5 sticky top-0" style={headStyle}>
                % Chg
              </th>
            </tr>
          </thead>
          <tbody>
            {held.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="py-8 text-center"
                  style={{ color: "var(--ink-faint)" }}
                >
                  No open positions — buy a symbol to get started.
                </td>
              </tr>
            )}
            {held.map((p) => {
              const livePrice = getLivePrice(p.ticker) ?? p.current_price;
              const marketValue = p.quantity * livePrice;
              const costBasis = p.quantity * p.avg_cost;
              const pnl = marketValue - costBasis;
              const pnlPct = costBasis > 0 ? (pnl / costBasis) * 100 : 0;
              const pnlColor =
                pnl > 0
                  ? "var(--up)"
                  : pnl < 0
                    ? "var(--down)"
                    : "var(--ink-dim)";
              const isSel = selected === p.ticker;
              return (
                <tr
                  key={p.ticker}
                  data-testid="position-row"
                  data-ticker={p.ticker}
                  onClick={() => onSelect(p.ticker)}
                  className="cursor-pointer"
                  style={{
                    borderBottom: "1px solid var(--border)",
                    background: isSel
                      ? "rgba(236,173,10,0.05)"
                      : "transparent",
                  }}
                >
                  <td className="px-3 py-2">
                    <span
                      className="font-bold tracking-wide"
                      style={{
                        color: isSel ? "var(--accent)" : "var(--ink)",
                      }}
                    >
                      {p.ticker}
                    </span>
                  </td>
                  <td
                    data-testid="position-qty"
                    className="tnum text-right px-3 py-2"
                    style={cellInk}
                  >
                    {fmtQty(p.quantity)}
                  </td>
                  <td className="tnum text-right px-3 py-2" style={cellDim}>
                    {fmtPrice(p.avg_cost)}
                  </td>
                  <td className="tnum text-right px-3 py-2" style={cellInk}>
                    {fmtPrice(livePrice)}
                  </td>
                  <td
                    className="tnum text-right px-3 py-2 font-semibold"
                    style={{ color: pnlColor }}
                  >
                    {fmtMoney(pnl, { sign: true })}
                  </td>
                  <td
                    className="tnum text-right px-3 py-2 font-semibold"
                    style={{ color: pnlColor }}
                  >
                    {fmtPct(pnlPct)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const headStyle: React.CSSProperties = {
  background: "var(--bg-panel)",
  borderBottom: "1px solid var(--border)",
};
const cellInk: React.CSSProperties = { color: "var(--ink)" };
const cellDim: React.CSSProperties = { color: "var(--ink-dim)" };
