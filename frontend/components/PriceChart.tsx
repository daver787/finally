"use client";

// PriceChart — main chart area. Lightweight Charts area series for the
// currently selected ticker, fed from SSE-accumulated history.

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { PricePoint, PriceSnapshot } from "@/lib/types";
import { fmtPct, fmtPrice } from "@/lib/format";

interface PriceChartProps {
  ticker: string | null;
  data: PricePoint[];
  snapshot?: PriceSnapshot;
}

export function PriceChart({ ticker, data, snapshot }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  // Direction-aware accent for the chart line.
  const up = (snapshot?.changePct ?? 0) >= 0;
  const lineColor = up ? "#2ecc71" : "#ff4d5e";

  // Create the chart once.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { color: "transparent" },
        textColor: "#8b97a8",
        fontFamily:
          "var(--font-mono), ui-monospace, SFMono-Regular, monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(35,45,63,0.5)" },
        horzLines: { color: "rgba(35,45,63,0.5)" },
      },
      rightPriceScale: { borderColor: "#232d3f" },
      timeScale: {
        borderColor: "#232d3f",
        timeVisible: true,
        secondsVisible: true,
      },
      crosshair: {
        vertLine: { color: "#324159", labelBackgroundColor: "#1a2231" },
        horzLine: { color: "#324159", labelBackgroundColor: "#1a2231" },
      },
      handleScroll: false,
      handleScale: false,
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#2ecc71",
      topColor: "rgba(46,204,113,0.28)",
      bottomColor: "rgba(46,204,113,0.0)",
      lineWidth: 2,
      priceLineVisible: true,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const resize = () => {
      if (!containerRef.current) return;
      chart.applyOptions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Push data + recolor on updates.
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    series.applyOptions({
      lineColor,
      topColor: up ? "rgba(46,204,113,0.28)" : "rgba(255,77,94,0.26)",
      bottomColor: up ? "rgba(46,204,113,0.0)" : "rgba(255,77,94,0.0)",
    });
    series.setData(
      data.map((p) => ({ time: p.time as Time, value: p.value })),
    );
    if (data.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [data, lineColor, up]);

  return (
    <div className="panel panel-in flex flex-col h-full overflow-hidden">
      <div className="panel-header">
        <div className="flex items-center gap-3">
          <span className="panel-title">Chart</span>
          {ticker && (
            <span
              className="text-sm font-extrabold tracking-wide"
              style={{ color: "var(--accent)" }}
            >
              {ticker}
            </span>
          )}
        </div>
        {snapshot && (
          <div className="flex items-baseline gap-3">
            <span
              className="tnum text-base font-bold"
              style={{ color: "var(--ink)" }}
            >
              {fmtPrice(snapshot.price)}
            </span>
            <span
              className="tnum text-xs font-semibold"
              style={{ color: up ? "var(--up)" : "var(--down)" }}
            >
              {fmtPct(snapshot.changePct)}
            </span>
          </div>
        )}
      </div>

      <div className="relative flex-1">
        <div ref={containerRef} className="absolute inset-0" />
        {(!ticker || data.length < 2) && (
          <div
            className="absolute inset-0 flex items-center justify-center text-xs pointer-events-none"
            style={{ color: "var(--ink-faint)" }}
          >
            {ticker
              ? "Accumulating live data…"
              : "Select a symbol from the watchlist"}
          </div>
        )}
      </div>
    </div>
  );
}
