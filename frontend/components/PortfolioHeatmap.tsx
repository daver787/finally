"use client";

// PortfolioHeatmap — Recharts Treemap. Each tile is a position sized by
// portfolio weight and colored by unrealized P&L.

import { Treemap, ResponsiveContainer } from "recharts";
import type { Position } from "@/lib/types";
import { fmtMoney, fmtPct } from "@/lib/format";

interface PortfolioHeatmapProps {
  positions: Position[];
  getLivePrice: (ticker: string) => number | undefined;
}

interface TileDatum {
  name: string;
  size: number;
  pnl: number;
  pnlPct: number;
  [key: string]: string | number;
}

// Map a P&L percentage to a green/red gradient fill.
function pnlFill(pnlPct: number): string {
  if (Math.abs(pnlPct) < 0.01) return "#1a2231";
  const clamped = Math.max(-8, Math.min(8, pnlPct));
  const intensity = Math.abs(clamped) / 8; // 0..1
  if (clamped > 0) {
    // dark -> bright green
    const r = Math.round(20 + intensity * 26);
    const g = Math.round(40 + intensity * 164);
    const b = Math.round(35 + intensity * 78);
    return `rgb(${r},${g},${b})`;
  }
  const r = Math.round(40 + intensity * 215);
  const g = Math.round(30 + intensity * 47);
  const b = Math.round(38 + intensity * 56);
  return `rgb(${r},${g},${b})`;
}

interface TileProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pnlPct?: number;
}

function Tile(props: TileProps) {
  const { x = 0, y = 0, width = 0, height = 0, name = "", pnlPct = 0 } = props;
  if (width <= 0 || height <= 0) return null;
  const showText = width > 44 && height > 28;
  const showPct = width > 56 && height > 44;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{
          fill: pnlFill(pnlPct),
          stroke: "#0d1117",
          strokeWidth: 2,
        }}
      />
      {showText && (
        <text
          x={x + width / 2}
          y={y + height / 2 - (showPct ? 7 : 0)}
          textAnchor="middle"
          dominantBaseline="middle"
          style={{
            fill: "#e6edf3",
            fontSize: 12,
            fontWeight: 700,
            fontFamily: "var(--font-mono), monospace",
          }}
        >
          {name}
        </text>
      )}
      {showPct && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 10}
          textAnchor="middle"
          dominantBaseline="middle"
          style={{
            fill: pnlPct >= 0 ? "#bff5d4" : "#ffd0d5",
            fontSize: 10,
            fontFamily: "var(--font-mono), monospace",
          }}
        >
          {fmtPct(pnlPct)}
        </text>
      )}
    </g>
  );
}

export function PortfolioHeatmap({
  positions,
  getLivePrice,
}: PortfolioHeatmapProps) {
  // Only positions with a non-zero quantity contribute tiles.
  const held = positions.filter((p) => p.quantity > 0);

  const data: TileDatum[] = held.map((p) => {
    const livePrice = getLivePrice(p.ticker) ?? p.current_price;
    const marketValue = p.quantity * livePrice;
    const costBasis = p.quantity * p.avg_cost;
    const pnl = marketValue - costBasis;
    const pnlPct = costBasis > 0 ? (pnl / costBasis) * 100 : 0;
    return {
      name: p.ticker,
      size: Math.max(marketValue, 0.01),
      pnl,
      pnlPct,
    };
  });

  return (
    <div
      data-testid="portfolio-heatmap"
      className="panel panel-in flex flex-col h-full overflow-hidden"
    >
      <div className="panel-header">
        <span className="panel-title">Portfolio Heatmap</span>
        <span className="text-[10px] tnum" style={{ color: "var(--ink-faint)" }}>
          {held.length} POSITIONS
        </span>
      </div>
      <div className="flex-1 p-1.5">
        {data.length === 0 ? (
          <div
            className="h-full flex items-center justify-center text-xs"
            style={{ color: "var(--ink-faint)" }}
          >
            No open positions
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={data}
              dataKey="size"
              nameKey="name"
              isAnimationActive={false}
              content={<Tile />}
            />
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
