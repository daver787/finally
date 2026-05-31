"use client";

// Singleton EventSource hook. Call ONCE at the TradingTerminal root component
// (TradingTerminal calls it from its function body) and never again — the
// effect uses an empty deps array and lives for the entire app lifetime.
//
// The mandatory `return () => es?.close()` cleanup prevents a 2nd EventSource
// from leaking under React StrictMode's intentional dev-only double-mount
// (PITFALLS.md #4). Without cleanup, you get one connection per StrictMode
// remount cycle and the backend sees double SSE traffic.

import { useEffect } from "react";
import { useStore } from "@/store";
import type { PriceUpdate } from "@/lib/types";

export function useSSE() {
  const setPrice = useStore((s) => s.setPrice);
  const setStatus = useStore((s) => s.setConnectionStatus);

  useEffect(() => {
    if (typeof window === "undefined") return;
    let es: EventSource | undefined;

    function connect() {
      const base = process.env.NEXT_PUBLIC_API_BASE ?? "";
      es = new EventSource(`${base}/api/stream/prices`);
      es.onopen = () => setStatus("connected");
      es.onmessage = (event) => {
        // Backend sends ALL tracked tickers in a single event keyed by symbol:
        //   data: {"AAPL": {...PriceUpdate}, "GOOGL": {...}, ...}
        // The `as` cast is a TS hint only — the JSON is rendered safely as
        // text by React JSX (T-02-02 in the threat register).
        const updates = JSON.parse(event.data) as Record<string, PriceUpdate>;
        for (const update of Object.values(updates)) {
          setPrice(update.ticker, update);
        }
      };
      es.onerror = () => {
        setStatus("reconnecting");
        if (es && es.readyState === EventSource.CLOSED) {
          setStatus("disconnected");
        }
      };
    }

    connect();
    return () => {
      es?.close();
      setStatus("disconnected");
    };
    // Empty deps — singleton SSE connection for the app lifetime (D-21).
    // Zustand setters are stable references so re-binding on every render
    // would only force redundant teardown/reconnect cycles.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
