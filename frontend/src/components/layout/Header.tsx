"use client";

// FinAlly header: logo (accent yellow) + live portfolio value + live cash +
// three-state connection dot (D-19, D-20).
//
// Portfolio + cash are REST-fetched on mount only — they will NOT update on
// every SSE tick (D-19 explicitly accepts staleness in Phase 1; Phase 3 will
// re-fetch after each trade execution). The .catch(() => {}) swallows any
// fetch error silently so a startup race against an uninitialized backend
// doesn't render a console error to the user.
//
// connectionStatus is subscribed via a dedicated selector. Four separate
// useStore selectors (not one object selector) keep re-renders surgical:
// only the slice the header reads triggers a re-render.
//
// Phase 3 adds an "Ask FinAlly" button (bg-purple) that toggles
// useStore.chatOpen; TradingTerminal observes that flag and renders ChatPanel
// as a slide-over overlay.

import { useEffect } from "react";
import { useStore } from "@/store";

const DOT_COLORS = {
  connected: "bg-[#2ea043]",
  reconnecting: "bg-[#d29922] connection-pulse",
  disconnected: "bg-[#da3633]",
};

export function Header() {
  const cash = useStore((s) => s.cash);
  const totalValue = useStore((s) => s.totalValue);
  const setPortfolio = useStore((s) => s.setPortfolio);
  const connectionStatus = useStore((s) => s.connectionStatus);
  const chatOpen = useStore((s) => s.chatOpen);
  const setChatOpen = useStore((s) => s.setChatOpen);

  useEffect(() => {
    fetch("/api/portfolio")
      .then((r) => r.json())
      .then((data) => setPortfolio(data.cash_balance, data.total_value))
      .catch(() => {});
  }, [setPortfolio]);

  return (
    <header className="flex items-center justify-between px-4 border-b border-border bg-bg-surface">
      <span className="font-mono font-bold text-accent text-lg">FinAlly</span>
      <div className="flex items-center gap-6 font-mono text-sm">
        <span className="text-text-secondary">Portfolio</span>
        <span className="text-text-primary font-bold">
          ${totalValue.toLocaleString("en-US", { minimumFractionDigits: 2 })}
        </span>
        <span className="text-text-secondary">Cash</span>
        <span className="text-text-primary">
          ${cash.toLocaleString("en-US", { minimumFractionDigits: 2 })}
        </span>
        <button
          type="button"
          onClick={() => setChatOpen(!chatOpen)}
          className="font-mono text-xs px-2 py-1 rounded bg-purple text-text-primary hover:opacity-90"
          aria-pressed={chatOpen}
        >
          Ask FinAlly
        </button>
        <span
          className={`w-2.5 h-2.5 rounded-full ${DOT_COLORS[connectionStatus]}`}
          title={connectionStatus}
          aria-label={`Connection ${connectionStatus}`}
        />
      </div>
    </header>
  );
}
