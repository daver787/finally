"use client";

// TradeBar — ticker + qty inputs, BUY/SELL buttons, 3s auto-dismiss toast.
// BUY uses bg-primary (locked decision); SELL uses bg-price-down (red).
// pending state disables all inputs and buttons during the network call.
// useEffect+setTimeout pattern (RESEARCH.md Pattern 4) prevents toast stacking.
//
// Ticker input syncs from useStore.selectedTicker via useEffect, so clicking
// a row in the watchlist auto-populates the trade form. Quantity is cleared
// on successful trade but the ticker is preserved for follow-on trades.

import { useState, useEffect, type FormEvent } from "react";
import clsx from "clsx";
import { useStore } from "@/store";
import { useTrade } from "@/hooks/useTrade";

type Toast = { kind: "success" | "error"; text: string };

export function TradeBar() {
  const [ticker, setTicker] = useState("");
  const [qty, setQty] = useState("");
  const [toast, setToast] = useState<Toast | null>(null);
  const [pending, setPending] = useState(false);

  const selectedTicker = useStore((s) => s.selectedTicker);
  const { submit } = useTrade();

  // Sync the ticker input when the user clicks a watchlist row. The effect's
  // purpose IS to mirror an external source (Zustand store) into local input
  // state — the set-state-in-effect rule's typical concern (cascading renders)
  // does not apply here because the source already changed in another component
  // (WatchlistRow's onClick → setSelectedTicker), not in this render. Same
  // pattern as useWatchlist.ts (fetch-on-mount → setTickers).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (selectedTicker) setTicker(selectedTicker);
  }, [selectedTicker]);

  // Auto-dismiss toast 3s after appearing. Cleanup on new toast / unmount
  // prevents stale timers stacking and flickering an old toast away while a
  // new one is showing.
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(id);
  }, [toast]);

  async function handle(
    side: "buy" | "sell",
    e: React.MouseEvent | FormEvent,
  ) {
    e.preventDefault();
    const q = parseFloat(qty);
    const t = ticker.trim().toUpperCase();
    if (!t || !Number.isFinite(q) || q <= 0) {
      setToast({ kind: "error", text: "Enter ticker and positive quantity" });
      return;
    }
    setPending(true);
    try {
      const result = await submit(side, t, q);
      setToast(
        result.ok
          ? {
              kind: "success",
              text: `${side.toUpperCase()} ${q} ${t} @ $${result.price?.toFixed(2)}`,
            }
          : { kind: "error", text: result.error ?? "Trade failed" },
      );
      if (result.ok) setQty("");
    } catch {
      setToast({ kind: "error", text: "Network error" });
    } finally {
      setPending(false);
    }
  }

  return (
    <form
      className="border-t border-border bg-bg-surface flex items-center gap-2 px-3 h-16"
      onSubmit={(e) => handle("buy", e)}
    >
      <input
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        placeholder="TICKER"
        aria-label="Ticker"
        disabled={pending}
        className="bg-bg-elevated border border-border rounded px-2 py-1 w-24 font-mono text-sm uppercase text-text-primary focus:outline-none focus:border-primary disabled:opacity-50"
      />
      <input
        value={qty}
        onChange={(e) => setQty(e.target.value)}
        placeholder="QTY"
        aria-label="Quantity"
        type="number"
        step="0.0001"
        min="0"
        disabled={pending}
        className="bg-bg-elevated border border-border rounded px-2 py-1 w-28 font-mono text-sm text-text-primary focus:outline-none focus:border-primary disabled:opacity-50"
      />
      <button
        type="button"
        onClick={(e) => handle("buy", e)}
        disabled={pending}
        className="bg-primary text-text-primary font-bold rounded px-4 py-1 text-sm disabled:opacity-50"
      >
        BUY
      </button>
      <button
        type="button"
        onClick={(e) => handle("sell", e)}
        disabled={pending}
        className="bg-price-down text-text-primary font-bold rounded px-4 py-1 text-sm disabled:opacity-50"
      >
        SELL
      </button>
      {toast && (
        <span
          role="status"
          aria-live="polite"
          className={clsx(
            "ml-2 text-xs font-mono px-2 py-1 rounded border",
            toast.kind === "success"
              ? "text-price-up border-price-up/40 bg-price-up/10"
              : "text-price-down border-price-down/40 bg-price-down/10",
          )}
        >
          {toast.text}
        </span>
      )}
    </form>
  );
}
