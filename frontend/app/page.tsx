"use client";

// FinAlly — single-page trading workstation.
// Orchestrates the SSE market stream, REST portfolio/watchlist state, and the
// AI chat copilot across a dense, terminal-style grid layout.

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useMarketStream } from "@/lib/useMarketStream";
import type {
  ChatMessage,
  HistoryPoint,
  Portfolio,
  TradeSide,
  WatchlistItem,
} from "@/lib/types";
import { Header } from "@/components/Header";
import { Watchlist } from "@/components/Watchlist";
import { WatchlistAdd } from "@/components/WatchlistAdd";
import { PriceChart } from "@/components/PriceChart";
import { PortfolioHeatmap } from "@/components/PortfolioHeatmap";
import { PnlChart } from "@/components/PnlChart";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { ChatPanel } from "@/components/ChatPanel";

const EMPTY_PORTFOLIO: Portfolio = {
  cash_balance: 0,
  total_value: 0,
  total_unrealized_pnl: 0,
  positions: [],
};

let chatIdSeq = 0;
const nextChatId = () => `msg-${Date.now()}-${chatIdSeq++}`;

export default function TradingTerminal() {
  const { prices, history, status, lastChanged, getPrice } = useMarketStream();

  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio>(EMPTY_PORTFOLIO);
  const [pnlHistory, setPnlHistory] = useState<HistoryPoint[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatBusy, setChatBusy] = useState(false);

  // ---- Data loaders -------------------------------------------------------
  const loadWatchlist = useCallback(async () => {
    try {
      const data = await api.getWatchlist();
      setWatchlist(data);
      setSelected((cur) => cur ?? data[0]?.ticker ?? null);
    } catch {
      // backend may not be up yet — SSE/retry will recover
    }
  }, []);

  const loadPortfolio = useCallback(async () => {
    try {
      setPortfolio(await api.getPortfolio());
    } catch {
      /* ignore transient errors */
    }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      setPnlHistory(await api.getHistory());
    } catch {
      /* ignore transient errors */
    }
  }, []);

  // Initial load.
  useEffect(() => {
    loadWatchlist();
    loadPortfolio();
    loadHistory();
  }, [loadWatchlist, loadPortfolio, loadHistory]);

  // Refresh P&L history every 30s.
  useEffect(() => {
    const id = window.setInterval(loadHistory, 30_000);
    return () => window.clearInterval(id);
  }, [loadHistory]);

  // Light portfolio refresh every 30s so server-side snapshots stay in sync.
  useEffect(() => {
    const id = window.setInterval(loadPortfolio, 30_000);
    return () => window.clearInterval(id);
  }, [loadPortfolio]);

  // ---- Live-derived header values ----------------------------------------
  // Recompute total value and P&L from live SSE prices between REST refreshes.
  const liveTotals = useMemo(() => {
    let positionsValue = 0;
    let costBasis = 0;
    for (const p of portfolio.positions) {
      if (p.quantity <= 0) continue;
      const price = getPrice(p.ticker) ?? p.current_price;
      positionsValue += p.quantity * price;
      costBasis += p.quantity * p.avg_cost;
    }
    return {
      totalValue: portfolio.cash_balance + positionsValue,
      totalPnl: positionsValue - costBasis,
    };
    // `prices` is intentionally a dep so totals refresh on every tick.
  }, [portfolio, prices, getPrice]);

  // ---- Actions ------------------------------------------------------------
  const handleAddWatchlist = useCallback(async (ticker: string) => {
    const updated = await api.addWatchlistTicker(ticker);
    setWatchlist(updated);
    setSelected(ticker.toUpperCase());
  }, []);

  const handleRemoveWatchlist = useCallback(
    async (ticker: string) => {
      try {
        await api.removeWatchlistTicker(ticker);
        setWatchlist((cur) => cur.filter((w) => w.ticker !== ticker));
        setSelected((cur) => (cur === ticker ? null : cur));
      } catch {
        loadWatchlist();
      }
    },
    [loadWatchlist],
  );

  const handleTrade = useCallback(
    async (ticker: string, quantity: number, side: TradeSide) => {
      const updated = await api.trade({ ticker, quantity, side });
      setPortfolio(updated);
      loadHistory();
    },
    [loadHistory],
  );

  const handleChatSend = useCallback(
    async (text: string) => {
      const userMsg: ChatMessage = {
        id: nextChatId(),
        role: "user",
        content: text,
      };
      setChatMessages((cur) => [...cur, userMsg]);
      setChatBusy(true);
      try {
        const res = await api.chat(text);
        setChatMessages((cur) => [
          ...cur,
          {
            id: nextChatId(),
            role: "assistant",
            content: res.message,
            trades: res.trades_executed,
            watchlistChanges: res.watchlist_changes_applied,
            errors: res.errors,
          },
        ]);
        // The AI may have traded or changed the watchlist — re-sync.
        loadPortfolio();
        loadWatchlist();
        loadHistory();
      } catch (e) {
        setChatMessages((cur) => [
          ...cur,
          {
            id: nextChatId(),
            role: "assistant",
            content:
              e instanceof Error
                ? `Sorry — I couldn't process that. ${e.message}`
                : "Sorry — something went wrong.",
            errors: [],
          },
        ]);
      } finally {
        setChatBusy(false);
      }
    },
    [loadPortfolio, loadWatchlist, loadHistory],
  );

  const selectedSnapshot = selected ? prices[selected] : undefined;
  const selectedHistory = selected ? (history[selected] ?? []) : [];

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Header
        totalValue={liveTotals.totalValue}
        cashBalance={portfolio.cash_balance}
        totalPnl={liveTotals.totalPnl}
        status={status}
        chatOpen={chatOpen}
        onToggleChat={() => setChatOpen((o) => !o)}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Main workspace */}
        <main className="flex-1 flex flex-col gap-2 p-2 overflow-hidden">
          {/* Top row: watchlist | chart | heatmap */}
          <div
            className="grid gap-2 flex-1 min-h-0"
            style={{ gridTemplateColumns: "300px 1fr 320px" }}
          >
            {/* Left column — watchlist + add */}
            <div className="flex flex-col gap-2 min-h-0">
              <div className="flex-1 min-h-0">
                <Watchlist
                  items={watchlist}
                  prices={prices}
                  history={history}
                  lastChanged={lastChanged}
                  selected={selected}
                  onSelect={setSelected}
                  onRemove={handleRemoveWatchlist}
                />
              </div>
              <WatchlistAdd onAdd={handleAddWatchlist} />
            </div>

            {/* Center — main chart */}
            <div className="min-h-0">
              <PriceChart
                ticker={selected}
                data={selectedHistory}
                snapshot={selectedSnapshot}
              />
            </div>

            {/* Right — heatmap */}
            <div className="min-h-0">
              <PortfolioHeatmap
                positions={portfolio.positions}
                getLivePrice={getPrice}
              />
            </div>
          </div>

          {/* Bottom row: positions | P&L chart */}
          <div
            className="grid gap-2 min-h-0"
            style={{ gridTemplateColumns: "1fr 1fr", height: 224 }}
          >
            <PositionsTable
              positions={portfolio.positions}
              getLivePrice={getPrice}
              onSelect={setSelected}
              selected={selected}
            />
            <PnlChart history={pnlHistory} />
          </div>

          {/* Trade bar */}
          <TradeBar defaultTicker={selected} onTrade={handleTrade} />
        </main>

        {/* AI copilot */}
        <ChatPanel
          open={chatOpen}
          messages={chatMessages}
          busy={chatBusy}
          onSend={handleChatSend}
          onClose={() => setChatOpen(false)}
        />
      </div>
    </div>
  );
}
