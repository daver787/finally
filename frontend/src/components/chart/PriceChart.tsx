"use client";

// Live Lightweight Charts v5 area chart for the currently selected ticker.
//
// Imperatively creates a single chart instance inside a ref'd div on mount.
// On ticker change (selectedTicker / sparkline / lastPrice deps), the full
// sparkline backlog is rebuilt with synthesized monotonic-integer-second
// timestamps and pushed via series.setData. On each subsequent SSE tick,
// series.update appends just the latest point in-place — no chart re-creation,
// no remount, no flicker on selection swap. lastAppendedTsRef dedupes
// tick appends if React rerenders without a new timestamp.
//
// SSR safety: this file is the dynamic target loaded only on the client
// by PriceChartArea (next/dynamic ssr:false). It must NEVER be imported
// directly by a server component.

import { useEffect, useRef } from "react";
import { createChart, AreaSeries } from "lightweight-charts";
import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import { useStore } from "@/store";

export default function PriceChart() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const lastAppendedTsRef = useRef<number | null>(null);

  const selectedTicker = useStore((s) => s.selectedTicker);
  const sparkline = useStore((s) =>
    s.selectedTicker ? s.sparklines[s.selectedTicker] : undefined,
  );
  const lastPrice = useStore((s) =>
    s.selectedTicker ? s.prices[s.selectedTicker] : undefined,
  );

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
    if (
      !seriesRef.current ||
      !selectedTicker ||
      !sparkline ||
      sparkline.length < 2 ||
      !lastPrice
    ) {
      return;
    }
    const anchor = Math.floor(lastPrice.timestamp);
    const points = sparkline.map((priceAtI, i) => {
      const t = anchor - (sparkline.length - 1 - i);
      return { time: t as Time, value: priceAtI };
    });
    seriesRef.current.setData(points);
    chartRef.current?.timeScale().fitContent();
    lastAppendedTsRef.current = anchor;
  }, [selectedTicker, sparkline, lastPrice]);

  useEffect(() => {
    if (!seriesRef.current || !selectedTicker || !lastPrice) return;
    const ts = Math.floor(lastPrice.timestamp);
    if (ts === lastAppendedTsRef.current) return;
    seriesRef.current.update({ time: ts as Time, value: lastPrice.price });
    lastAppendedTsRef.current = ts;
  }, [selectedTicker, lastPrice]);

  return <div ref={containerRef} className="w-full h-full" />;
}
