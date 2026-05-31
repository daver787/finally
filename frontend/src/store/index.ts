// Zustand store for live price data + connection status + portfolio summary.
//
// Per-component selectors (e.g., `useStore(s => s.prices[ticker])`) keep
// renders isolated to the ticker that ticked — no full-store re-render storms
// for the 10-ticker watchlist (PITFALLS.md re-render storm class of risk).
//
// `setPrice` updates both `prices[ticker]` and `sparklines[ticker]` in a single
// `set()` call. Sparkline arrays are capped at 100 entries via FIFO slicing
// (`slice(-99)` then append) per D-15.
//
// Portfolio coexistence (Plan 02-01): the original `setPortfolio(cash,
// totalValue)` two-arg setter is preserved unchanged because Header.tsx
// already calls it. The new `portfolio` slice holds the FULL /api/portfolio
// response (positions + cash + total) for Phase 2 consumers, and the new
// `setPortfolioSummary` writes that whole object. The two coexist by design.
//
// chatOpen is the only chat state in Zustand — it bridges Header (toggle
// button) to TradingTerminal (conditional render). Messages live in useChat
// local state per D-18 — same pattern as watchlist tickers.

import { create } from "zustand";
import type {
  PriceUpdate,
  PortfolioSummary,
  PortfolioHistoryPoint,
} from "@/lib/types";

interface StoreState {
  prices: Record<string, PriceUpdate>;
  sparklines: Record<string, number[]>;
  connectionStatus: "connected" | "reconnecting" | "disconnected";
  cash: number;
  totalValue: number;
  // Raw /api/portfolio response (Phase 2). `cash` and `totalValue` above are
  // populated by the legacy `setPortfolio` so Header-only callers keep working.
  portfolio: PortfolioSummary | null;
  portfolioHistory: PortfolioHistoryPoint[];
  selectedTicker: string | null;
  chatOpen: boolean;
  setPrice: (ticker: string, update: PriceUpdate) => void;
  setConnectionStatus: (s: StoreState["connectionStatus"]) => void;
  setPortfolio: (cash: number, totalValue: number) => void;
  setPortfolioSummary: (summary: PortfolioSummary | null) => void;
  setPortfolioHistory: (history: PortfolioHistoryPoint[]) => void;
  setSelectedTicker: (ticker: string | null) => void;
  setChatOpen: (open: boolean) => void;
}

export const useStore = create<StoreState>()((set) => ({
  prices: {},
  sparklines: {},
  connectionStatus: "disconnected",
  cash: 10000,
  totalValue: 10000,
  portfolio: null,
  portfolioHistory: [],
  selectedTicker: null,
  chatOpen: false,
  setPrice: (ticker, update) =>
    set((state) => ({
      prices: { ...state.prices, [ticker]: update },
      sparklines: {
        ...state.sparklines,
        [ticker]: [
          ...(state.sparklines[ticker] ?? []).slice(-99),
          update.price,
        ],
      },
    })),
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  setPortfolio: (cash, totalValue) => set({ cash, totalValue }),
  setPortfolioSummary: (summary) => set({ portfolio: summary }),
  setPortfolioHistory: (history) => set({ portfolioHistory: history }),
  setSelectedTicker: (ticker) => set({ selectedTicker: ticker }),
  setChatOpen: (open) => set({ chatOpen: open }),
}));
