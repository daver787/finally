"use client";

// PnlChart — total portfolio value over time, from /api/portfolio/history.

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoryPoint } from "@/lib/types";
import { fmtMoney } from "@/lib/format";

interface PnlChartProps {
  history: HistoryPoint[];
}

interface ChartDatum {
  t: string;
  label: string;
  value: number;
}

interface TooltipPayload {
  payload: ChartDatum;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload;
  return (
    <div
      className="px-2.5 py-1.5 rounded text-xs"
      style={{
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-bright)",
      }}
    >
      <div className="tnum font-bold" style={{ color: "var(--ink)" }}>
        {fmtMoney(d.value)}
      </div>
      <div className="tnum text-[10px]" style={{ color: "var(--ink-faint)" }}>
        {d.label}
      </div>
    </div>
  );
}

export function PnlChart({ history }: PnlChartProps) {
  const data: ChartDatum[] = history.map((h) => {
    const date = new Date(h.recorded_at);
    return {
      t: h.recorded_at,
      label: Number.isNaN(date.getTime())
        ? h.recorded_at
        : date.toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          }),
      value: h.total_value,
    };
  });

  const first = data[0]?.value ?? 0;
  const last = data[data.length - 1]?.value ?? 0;
  const up = last >= first;
  const stroke = up ? "#2ecc71" : "#ff4d5e";

  return (
    <div
      data-testid="pnl-chart"
      className="panel panel-in flex flex-col h-full overflow-hidden"
    >
      <div className="panel-header">
        <span className="panel-title">Portfolio Value</span>
        {data.length > 1 && (
          <span
            className="tnum text-[10px] font-semibold"
            style={{ color: stroke }}
          >
            {fmtMoney(last - first, { sign: true })}
          </span>
        )}
      </div>
      <div className="flex-1 p-1.5">
        {data.length < 2 ? (
          <div
            className="h-full flex items-center justify-center text-xs"
            style={{ color: "var(--ink-faint)" }}
          >
            Building value history…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 6, right: 6, bottom: 0, left: -16 }}
            >
              <defs>
                <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity={0.32} />
                  <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="label"
                tick={{ fill: "#56627a", fontSize: 9 }}
                axisLine={{ stroke: "#232d3f" }}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fill: "#56627a", fontSize: 9 }}
                axisLine={{ stroke: "#232d3f" }}
                tickLine={false}
                width={56}
                tickFormatter={(v: number) => `$${Math.round(v / 1000)}k`}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ stroke: "#324159" }}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={stroke}
                strokeWidth={2}
                fill="url(#pnlFill)"
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
