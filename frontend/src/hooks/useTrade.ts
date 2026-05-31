"use client";

// useTrade — submit() POSTs a trade and refreshes the portfolio slice in Zustand on success.
// Uses useStore.getState() (not useStore(selector)) to avoid subscribing this hook to store updates —
// the hook stays free of re-render dependencies on the very state it writes.
//
// On a successful trade we ALSO call setPortfolio(cash, totalValue) (the legacy two-arg setter
// Header.tsx subscribes to via s.cash / s.totalValue) so the header updates immediately without
// waiting for the 10s usePortfolio() poll. The /history refetch lets the P&L chart pick up the
// post-trade snapshot the backend wrote inside the same request.

import { useStore } from "@/store";
import { postTrade, fetchPortfolio, fetchPortfolioHistory } from "@/lib/api";
import type { TradeResult } from "@/lib/types";

export function useTrade(): {
  submit: (
    side: "buy" | "sell",
    ticker: string,
    quantity: number,
  ) => Promise<TradeResult>;
} {
  async function submit(
    side: "buy" | "sell",
    ticker: string,
    quantity: number,
  ): Promise<TradeResult> {
    const result = await postTrade({ side, ticker, quantity });
    if (result.ok) {
      // Refresh portfolio in the background — do NOT await here. Returning
      // result immediately lets TradeBar clear pending+show the toast right
      // away, decoupling the trade confirmation from the portfolio fetch.
      // If the fetch hangs (e.g. slow backend), the trade toast still appears
      // and the next usePortfolio() poll (≤10s) corrects the UI.
      void (async () => {
        try {
          const [summary, history] = await Promise.all([
            fetchPortfolio(),
            fetchPortfolioHistory(),
          ]);
          const { setPortfolioSummary, setPortfolioHistory, setPortfolio } =
            useStore.getState();
          setPortfolioSummary(summary);
          setPortfolioHistory(history);
          setPortfolio(summary.cash_balance, summary.total_value);
        } catch (err) {
          console.error("useTrade: post-trade refresh failed", err);
        }
      })();
    }
    return result;
  }

  return { submit };
}
