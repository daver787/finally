"use client";

// REST-backed watchlist hook. Per D-18 the tickers list is NOT in Zustand —
// useState is sufficient for a single-component list that mutates only on
// user action. Refetches via GET /api/watchlist after every mutation so the
// UI sees the server's normalized view (uppercase, dedup'd) without local
// reconciliation logic.
//
// addTicker returns {ok, error?} so the caller (WatchlistPanel) can render
// the server's 400 detail inline below the form (D-09). removeTicker is
// fire-and-refetch — no confirmation dialog (D-10).
//
// encodeURIComponent on the DELETE path is good hygiene; tickers are uppercase
// A-Z so it's a no-op in practice, but mitigates T-03-04 (path-injection via
// stale list state) defensively.

import { useState, useEffect, useCallback } from "react";
import type { WatchlistEntry } from "@/lib/types";

export function useWatchlist() {
  const [tickers, setTickers] = useState<WatchlistEntry[]>([]);

  const fetchWatchlist = useCallback(async () => {
    try {
      const r = await fetch("/api/watchlist");
      if (r.ok) {
        setTickers(await r.json());
      }
    } catch {
      // Network error (e.g. transient on dev startup) — tickers stay as-is
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount is the side effect — eslint rule
    // react-hooks/set-state-in-effect doesn't apply when the effect's purpose
    // IS to populate state from an external source (REST endpoint here).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchWatchlist();
  }, [fetchWatchlist]);

  async function addTicker(
    ticker: string,
  ): Promise<{ ok: boolean; error?: string }> {
    const r = await fetch("/api/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    });
    if (r.ok) {
      await fetchWatchlist();
      return { ok: true };
    }
    const body = await r.json().catch(() => ({}));
    return { ok: false, error: body.detail ?? "Failed to add ticker" };
  }

  async function removeTicker(ticker: string) {
    await fetch(`/api/watchlist/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    });
    await fetchWatchlist();
  }

  return { tickers, addTicker, removeTicker, refetch: fetchWatchlist };
}
