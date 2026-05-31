"use client";

// Recharts Treemap rendering the user's positions sized by portfolio weight
// and colored by sign of unrealized P&L. This file is the client-only target
// of next/dynamic ssr:false (PortfolioHeatmap.tsx) — recharts reads `window`
// at module-import time and would otherwise crash `next build` under
// output: 'export'.
//
// Cell value (`size`) uses Math.max(0, current_price ?? avg_cost) * quantity
// so the Treemap never sees a negative or NaN value (T-02-01) and so that
// rows whose SSE price has not yet arrived still appear (using avg_cost as
// the fallback).
//
// Cell color is red ONLY when unrealized_pnl is explicitly < 0; the
// null-unrealized-pnl case is treated as neutral-green (the position is at
// worst "unchanged"). Custom HeatmapCell renders ticker + percent labels
// inside cells large enough to fit them (>= 40w x >= 24h).

import { Treemap, ResponsiveContainer } from "recharts";
import type { PositionEntry } from "@/lib/types";

interface PortfolioHeatmapClientProps {
  positions: PositionEntry[];
  totalValue: number;
}

interface HeatmapDatum {
  name: string;
  ticker: string;
  size: number;
  fill: string;
  pnl_percent: number | null;
  // Recharts' TreemapDataType requires an open-ended index signature so its
  // generic dataKey/nameKey accessors can read arbitrary fields. We narrow
  // the value type to the union of our concrete field types.
  [key: string]: string | number | null;
}

// Recharts passes its computed TreemapNode props (x, y, width, height, name,
// fill, value, payload) into the custom content renderer. We type the props
// loosely here because Recharts' own type for the content callback is
// `TreemapContentType = ReactNode | ((props: TreemapNode) => React.ReactElement)`
// and TreemapNode carries an open-ended index signature.
interface HeatmapCellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  fill?: string;
  payload?: HeatmapDatum;
  pnl_percent?: number | null;
}

function HeatmapCell(props: HeatmapCellProps) {
  const x = props.x ?? 0;
  const y = props.y ?? 0;
  const width = props.width ?? 0;
  const height = props.height ?? 0;
  const fill = props.fill ?? "#26a641";
  const name = props.name ?? "";
  // Recharts spreads the data row fields onto the props object (alongside
  // x/y/width/height) — payload is not always populated by the cell renderer
  // path. Read pnl_percent from either site.
  const pnl_percent =
    props.payload?.pnl_percent ??
    (typeof props.pnl_percent === "number" ? props.pnl_percent : null);

  const showLabels = width >= 40 && height >= 24;

  return (
    <g style={{ pointerEvents: "none" }}>
      <rect x={x} y={y} width={width} height={height} fill={fill} stroke="#30363d" />
      {showLabels ? (
        <>
          <text
            x={x + width / 2}
            y={y + height / 2 - 4}
            textAnchor="middle"
            fill="#ffffff"
            fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
            fontWeight="bold"
            fontSize={12}
            style={{ pointerEvents: "none" }}
          >
            {name}
          </text>
          {pnl_percent != null ? (
            <text
              x={x + width / 2}
              y={y + height / 2 + 10}
              textAnchor="middle"
              fill="#e6edf3"
              fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
              fontSize={10}
              style={{ pointerEvents: "none" }}
            >
              {pnl_percent.toFixed(1) + "%"}
            </text>
          ) : null}
        </>
      ) : null}
    </g>
  );
}

export default function PortfolioHeatmapClient({
  positions,
  totalValue,
}: PortfolioHeatmapClientProps) {
  if (positions.filter((p) => p.quantity > 0).length === 0 || totalValue <= 0) {
    return (
      <div className="w-full h-full flex items-center justify-center text-text-muted text-sm font-mono">
        No positions to display
      </div>
    );
  }

  // Filter out zero-quantity positions (backend preserves qty=0 rows on full
  // sell; Recharts Treemap produces NaN pixel coords for size=0 cells).
  const data: HeatmapDatum[] = positions
    .filter((p) => p.quantity > 0)
    .map((position) => {
      const priceForSize =
        position.current_price ?? position.avg_cost;
      const size = Math.max(0.001, priceForSize * position.quantity);
      const fill =
        position.unrealized_pnl != null && position.unrealized_pnl < 0
          ? "#f85149"
          : "#26a641";
      return {
        name: position.ticker,
        ticker: position.ticker,
        size,
        fill,
        pnl_percent: position.pnl_percent,
      };
    });

  return (
    <ResponsiveContainer width="100%" height="100%">
      <Treemap
        data={data}
        dataKey="size"
        stroke="#30363d"
        aspectRatio={1}
        content={<HeatmapCell />}
        isAnimationActive={false}
      />
    </ResponsiveContainer>
  );
}
