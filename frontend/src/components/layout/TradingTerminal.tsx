"use client";

// Trading-terminal layout shell. CSS Grid spine for the whole app.
//
// Plan 03 replaces the Plan 02 walking-skeleton single-ticker header with the
// real <Header /> (portfolio + cash + connection dot) and swaps the left
// placeholder for <WatchlistPanel /> (10 seeded tickers, live prices,
// sparklines, add/remove).
// Center main now hosts the live price chart (Plan 02-02); the trade bar
// (Phase 3) replaces the placeholder slot — wired to POST /api/portfolio/trade
// via useTrade.
// Right aside now hosts the portfolio panel (Plan 02-03).
//
// Phase 3 adds <ChatPanel /> overlay rendered when useStore.chatOpen is true
// — slides over the right portfolio aside via absolute z-10 positioning.
//
// useSSE() is called exactly once here per D-21: a single EventSource for the
// whole app lifetime. <Header /> and <WatchlistPanel /> subscribe to the
// resulting Zustand state via their own per-ticker / per-field selectors.

import { useSSE } from "@/hooks/useSSE";
import { useStore } from "@/store";
import { Header } from "./Header";
import { WatchlistPanel } from "@/components/watchlist/WatchlistPanel";
import PriceChartArea from "@/components/chart/PriceChartArea";
import PortfolioPanel from "@/components/portfolio/PortfolioPanel";
import { TradeBar } from "@/components/trade/TradeBar";
import ChatPanel from "@/components/chat/ChatPanel";

export function TradingTerminal() {
  useSSE();
  const chatOpen = useStore((s) => s.chatOpen);

  return (
    <div className="h-screen grid grid-rows-[48px_1fr] bg-bg-base overflow-hidden">
      <Header />
      <div className="grid grid-cols-[280px_1fr_360px] overflow-hidden relative">
        <WatchlistPanel />
        <main className="grid grid-rows-[1fr_64px] overflow-hidden">
          <PriceChartArea />
          <TradeBar />
        </main>
        <aside className="overflow-hidden">
          <PortfolioPanel />
        </aside>
        {chatOpen && (
          <div className="absolute right-0 top-0 bottom-0 w-[360px] z-10">
            <ChatPanel />
          </div>
        )}
      </div>
    </div>
  );
}
