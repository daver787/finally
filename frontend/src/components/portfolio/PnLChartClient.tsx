"use client";

// Lightweight Charts v5 area chart for the portfolio's total_value over time.
//
// SSR safety: this file is the dynamic target loaded only on the client
// by PnLChart (next/dynamic ssr:false). It must NEVER be imported
// directly by a server component — lightweight-charts reads `window` at
// module-import time and would crash `next build` under output: 'export'.
//
// History from usePortfolio() comes in as PortfolioHistoryPoint[] with
// ISO timestamp strings; we parse each `recorded_at` to integer Unix
// seconds, filter NaN, sort ascending, and de-dup by time before passing
// to series.setData — Lightweight Charts v5 requires strictly monotonic
// integer-second times (T-02-03).

import { useEffect, useRef } from "react";
import { createChart, AreaSeries } from "lightweight-charts";
import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import type { PortfolioHistoryPoint } from "@/lib/types";

interface PnLChartClientProps {
  history: PortfolioHistoryPoint[];
}

export default function PnLChartClient({ history }: PnLChartClientProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (containerRef.current === null) return;
    const container = containerRef.current;
    const chart = createChart(container, {
      layout: {
        background: { color: "#0d1117" },
        textColor: "#8b949e",
      },
      grid: {
        vertLines: { color: "#30363d" },
        horzLines: { color: "#30363d" },
      },
      width: container.clientWidth,
      height: container.clientHeight,
      timeScale: {
        timeVisible: true,
        secondsVisible: true,
        borderColor: "#30363d",
      },
      rightPriceScale: {
        borderColor: "#30363d",
      },
      crosshair: {
        mode: 0,
      },
    });
    seriesRef.current = chart.addSeries(AreaSeries, {
      lineColor: "#209dd7",
      topColor: "rgba(32,157,215,0.4)",
      bottomColor: "rgba(32,157,215,0)",
      lineWidth: 2,
    });
    chartRef.current = chart;

    const resizeObserver = new ResizeObserver(() => {
      chart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight,
      });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    // Parse → filter NaN → sort ascending → de-dup by time. Lightweight
    // Charts v5 throws on non-monotonic timestamps; this absorbs any
    // duplicate-second or out-of-order snapshots produced by the backend.
    const parsed = history
      .map((point) => ({
        time: Math.floor(new Date(point.recorded_at).getTime() / 1000),
        value: point.total_value,
      }))
      .filter((p) => !Number.isNaN(p.time));
    parsed.sort((a, b) => a.time - b.time);
    const deduped: { time: Time; value: number }[] = [];
    let lastTime: number | null = null;
    for (const p of parsed) {
      if (p.time === lastTime) continue;
      deduped.push({ time: p.time as Time, value: p.value });
      lastTime = p.time;
    }
    seriesRef.current.setData(deduped);
    chartRef.current?.timeScale().fitContent();
  }, [history]);

  return <div ref={containerRef} className="w-full h-full" />;
}
