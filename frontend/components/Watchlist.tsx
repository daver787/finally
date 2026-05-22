"use client";

import { useEffect, useRef, useState } from "react";
import type {
  Direction,
  PricePoint,
  PriceSnapshot,
  WatchlistItem,
} from "@/lib/types";
import { fmtPct, fmtPrice } from "@/lib/format";
import { Sparkline } from "./Sparkline";

interface WatchlistProps {
  items: WatchlistItem[];
  prices: Record<string, PriceSnapshot>;
  history: Record<string, PricePoint[]>;
  lastChanged: Record<string, Direction>;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => void;
}

export function Watchlist({
  items,
  prices,
  history,
  lastChanged,
  selected,
  onSelect,
  onRemove,
}: WatchlistProps) {
  return (
    <div className="panel panel-in flex flex-col h-full overflow-hidden">
      <div className="panel-header">
        <span className="panel-title">Watchlist</span>
        <span
          className="text-[10px] tnum"
          style={{ color: "var(--ink-faint)" }}
        >
          {items.length} SYMBOLS
        </span>
      </div>

      <div
        className="grid items-center px-3 py-1.5 text-[9px] font-bold tracking-[0.1em] uppercase shrink-0"
        style={{
          gridTemplateColumns: "1fr 80px 70px 96px 20px",
          color: "var(--ink-faint)",
          borderBottom: "1px solid var(--border)",
          gap: "8px",
        }}
      >
        <span>Symbol</span>
        <span className="text-right">Last</span>
        <span className="text-right">Chg%</span>
        <span className="text-right">Trend</span>
        <span />
      </div>

      <div className="flex-1 overflow-y-auto">
        {items.length === 0 && (
          <div
            className="py-8 text-center text-xs"
            style={{ color: "var(--ink-faint)" }}
          >
            No symbols. Add one below.
          </div>
        )}
        {items.map((item) => (
          <WatchlistRow
            key={item.ticker}
            item={item}
            snapshot={prices[item.ticker]}
            series={history[item.ticker] ?? []}
            changeDir={lastChanged[item.ticker]}
            selected={selected === item.ticker}
            onSelect={() => onSelect(item.ticker)}
            onRemove={() => onRemove(item.ticker)}
          />
        ))}
      </div>
    </div>
  );
}

function WatchlistRow({
  item,
  snapshot,
  series,
  changeDir,
  selected,
  onSelect,
  onRemove,
}: {
  item: WatchlistItem;
  snapshot?: PriceSnapshot;
  series: PricePoint[];
  changeDir?: Direction;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const rowRef = useRef<HTMLDivElement>(null);
  const [flashCount, setFlashCount] = useState(0);

  // Live values fall back to the REST-provided snapshot.
  const price = snapshot?.price ?? item.price;
  const changePct = snapshot?.changePct ?? item.change_pct;

  // Trigger a flash whenever a new tick for this ticker arrives.
  useEffect(() => {
    if (!changeDir || changeDir === "flat") return;
    const el = rowRef.current;
    if (!el) return;
    el.classList.remove("flash-green", "flash-red");
    // force reflow so the animation restarts even on rapid ticks
    void el.offsetWidth;
    el.classList.add(changeDir === "up" ? "flash-green" : "flash-red");
    const id = window.setTimeout(() => {
      el.classList.remove("flash-green", "flash-red");
    }, 560);
    return () => window.clearTimeout(id);
    // flashCount is bumped per tick to re-run even when direction repeats
  }, [changeDir, flashCount]);

  useEffect(() => {
    if (snapshot) setFlashCount((c) => c + 1);
  }, [snapshot?.timestamp, snapshot?.price]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirColor =
    changePct == null
      ? "var(--ink-dim)"
      : changePct > 0
        ? "var(--up)"
        : changePct < 0
          ? "var(--down)"
          : "var(--ink-dim)";

  return (
    <div
      ref={rowRef}
      data-testid="watchlist-row"
      data-ticker={item.ticker}
      onClick={onSelect}
      className="group grid items-center px-3 py-2 cursor-pointer"
      style={{
        gridTemplateColumns: "1fr 80px 70px 96px 20px",
        gap: "8px",
        borderBottom: "1px solid var(--border)",
        borderLeft: selected
          ? "2px solid var(--accent)"
          : "2px solid transparent",
        background: selected ? "rgba(236,173,10,0.05)" : "transparent",
      }}
    >
      <div className="flex flex-col">
        <span
          className="font-bold text-[13px] tracking-wide"
          style={{ color: selected ? "var(--accent)" : "var(--ink)" }}
        >
          {item.ticker}
        </span>
      </div>

      <span
        data-testid="watchlist-price"
        className="tnum text-right text-[13px] font-semibold"
        style={{ color: "var(--ink)" }}
      >
        {fmtPrice(price)}
      </span>

      <span
        className="tnum text-right text-xs font-semibold"
        style={{ color: dirColor }}
      >
        {fmtPct(changePct)}
      </span>

      <div className="flex justify-end">
        <Sparkline data={series} color={dirColor} />
      </div>

      <button
        data-testid="watchlist-remove-btn"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="opacity-0 group-hover:opacity-100 transition-opacity text-sm leading-none"
        style={{ color: "var(--ink-faint)" }}
        aria-label={`Remove ${item.ticker}`}
        title={`Remove ${item.ticker}`}
      >
        ×
      </button>
    </div>
  );
}
