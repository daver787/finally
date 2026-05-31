"use client";

// React.memo'd row keyed by ticker. Per-ticker Zustand selectors keep this row
// from re-rendering when other tickers tick (D-17 prevents the 10-ticker
// re-render storm). The price span uses a useRef + void offsetWidth reflow
// technique to restart the CSS @keyframes animation on each price change
// without a full DOM remount or setTimeout.
//
// Hovering the row reveals an × button (D-10) that calls onRemove. The
// e.stopPropagation in the × handler prevents the row's onClick (which sets
// selectedTicker for the Phase 2 chart) from firing when the user removes.

import { memo, useEffect, useRef } from "react";
import { useStore } from "@/store";
import { Sparkline } from "./Sparkline";

const EMPTY_SPARKLINE: number[] = [];

interface WatchlistRowProps {
  ticker: string;
  onRemove: () => void;
}

export const WatchlistRow = memo(function WatchlistRow({
  ticker,
  onRemove,
}: WatchlistRowProps) {
  const priceUpdate = useStore((s) => s.prices[ticker]);
  const sparklineData = useStore((s) => s.sparklines[ticker] ?? EMPTY_SPARKLINE);
  const setSelectedTicker = useStore((s) => s.setSelectedTicker);
  const priceSpanRef = useRef<HTMLSpanElement>(null);
  const prevTimestampRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const el = priceSpanRef.current;
    if (!el || !priceUpdate || priceUpdate.timestamp === prevTimestampRef.current) return;
    prevTimestampRef.current = priceUpdate.timestamp;
    if (priceUpdate.direction === "flat") return;
    const cls = priceUpdate.direction === "up" ? "price-flash-up" : "price-flash-down";
    el.classList.remove("price-flash-up", "price-flash-down");
    void el.offsetWidth; // force reflow so removing+re-adding the class restarts the animation
    el.classList.add(cls);
  }, [priceUpdate]);

  const changeColor =
    (priceUpdate?.change_percent ?? 0) >= 0
      ? "text-price-up"
      : "text-price-down";

  return (
    <div
      className="group flex items-center gap-2 px-3 py-1.5 hover:bg-bg-elevated border-b border-border/50 cursor-pointer"
      onClick={() => setSelectedTicker(ticker)}
    >
      <span className="font-mono font-bold text-text-primary text-sm w-14 shrink-0">
        {ticker}
      </span>
      <span
        ref={priceSpanRef}
        className="font-mono text-sm text-text-primary w-16 text-right shrink-0 rounded px-0.5"
      >
        {priceUpdate ? priceUpdate.price.toFixed(2) : "—"}
      </span>
      <span
        className={`font-mono text-xs w-14 text-right shrink-0 ${changeColor}`}
      >
        {priceUpdate
          ? `${priceUpdate.change_percent >= 0 ? "▲" : "▼"} ${Math.abs(priceUpdate.change_percent).toFixed(2)}%`
          : "—"}
      </span>
      <div className="flex-1 flex justify-end items-center relative">
        <span className="group-hover:hidden">
          <Sparkline prices={sparklineData} />
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="hidden group-hover:block text-text-muted hover:text-price-down text-lg leading-none"
          aria-label={`Remove ${ticker}`}
        >
          ×
        </button>
      </div>
    </div>
  );
});
