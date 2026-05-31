"use client";

// Container for the watchlist sidebar: title bar + scrolling row list +
// inline add-ticker form + error display.
//
// The list comes from useWatchlist (REST + useState — D-18). Empty state per
// D-12 renders "Add a ticker above" in muted gray.
//
// Add-ticker flow: normalize via input.trim().toUpperCase() so a lowercase
// 'pypl' submission becomes 'PYPL' (matches backend normalization, mitigates
// T-03-03). Empty submissions are dropped client-side (no network call).
// On 400 the server's body.detail string is rendered as JSX text below the
// form (auto-escaped, T-03-02).

import { useState, type FormEvent } from "react";
import { useWatchlist } from "@/hooks/useWatchlist";
import { WatchlistRow } from "./WatchlistRow";

export function WatchlistPanel() {
  const { tickers, addTicker, removeTicker } = useWatchlist();
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const normalized = input.trim().toUpperCase();
    if (!normalized) return;
    const result = await addTicker(normalized);
    if (result.ok) {
      setInput("");
    } else {
      setError(result.error ?? "Invalid ticker");
    }
  }

  return (
    <aside className="flex flex-col border-r border-border bg-bg-surface overflow-hidden">
      <div className="px-3 py-2 border-b border-border text-xs text-text-secondary uppercase tracking-wider">
        Watchlist
      </div>
      <div className="flex-1 overflow-y-auto">
        {tickers.length === 0 ? (
          <p className="text-center text-text-muted text-sm mt-8">
            Add a ticker above
          </p>
        ) : (
          tickers.map((t) => (
            <WatchlistRow
              key={t.ticker}
              ticker={t.ticker}
              onRemove={() => removeTicker(t.ticker)}
            />
          ))
        )}
      </div>
      <form
        onSubmit={handleAdd}
        className="p-2 border-t border-border flex gap-1"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Add ticker…"
          className="flex-1 bg-bg-elevated border border-border rounded px-2 py-1 text-xs font-mono text-text-primary placeholder-text-muted focus:outline-none focus:border-primary"
        />
        <button
          type="submit"
          className="px-2 py-1 bg-purple rounded text-xs text-white"
        >
          +
        </button>
      </form>
      {error && <p className="px-2 pb-1 text-xs text-price-down">{error}</p>}
    </aside>
  );
}
