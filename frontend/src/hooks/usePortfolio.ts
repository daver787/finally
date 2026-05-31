"use client";

// usePortfolio — single fetch-and-merge entrypoint for Phase 2 portfolio
// consumers (P&L chart, positions table, treemap).
//
// Behaviour: on mount and every 10s thereafter, fetches /api/portfolio AND
// /api/portfolio/history in parallel and writes both into the Zustand store
// (also keeps the legacy `setPortfolio(cash, totalValue)` slice in sync so
// Header.tsx stays current). Errors are swallowed silently, matching the
// existing Header.tsx pattern. The /history backend route is not yet
// implemented — fetchPortfolioHistory absorbs that as [] (see lib/api.ts).
//
// Derived positions: useMemo merges `prices[ticker]` (SSE-fed) into each
// PositionEntry so consumers receive live current_price / unrealized_pnl /
// pnl_percent without owning the merge logic themselves. The original
// portfolio.positions array is never mutated.

import { useEffect, useMemo } from "react";
import { useStore } from "@/store";
import { fetchPortfolio, fetchPortfolioHistory } from "@/lib/api";
import type {
  PositionEntry,
  PortfolioSummary,
  PortfolioHistoryPoint,
} from "@/lib/types";

export function usePortfolio(): {
  portfolio: PortfolioSummary | null;
  positions: PositionEntry[];
  history: PortfolioHistoryPoint[];
} {
  const portfolio = useStore((s) => s.portfolio);
  const history = useStore((s) => s.portfolioHistory);
  const setPortfolioSummary = useStore((s) => s.setPortfolioSummary);
  const setPortfolioHistory = useStore((s) => s.setPortfolioHistory);
  const setPortfolioLegacy = useStore((s) => s.setPortfolio);
  // Subscribing to `prices` re-renders this hook's caller on every SSE tick.
  // That is intentional: Phase 2's PortfolioPanel is small, and the
  // alternative (duplicating merge logic per consumer) is worse.
  const prices = useStore((s) => s.prices);

  useEffect(() => {
    async function load() {
      try {
        const [summary, historyArr] = await Promise.all([
          fetchPortfolio(),
          fetchPortfolioHistory(),
        ]);
        setPortfolioSummary(summary);
        setPortfolioHistory(historyArr);
        setPortfolioLegacy(summary.cash_balance, summary.total_value);
      } catch {
        // Swallow — matches Header.tsx pattern. Avoids surfacing backend
        // internals to the dev console during a startup race.
      }
    }
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
    // Zustand setters are stable references; empty deps prevent a
    // teardown/reconnect cycle on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const positions = useMemo<PositionEntry[]>(() => {
    const rows = portfolio?.positions ?? [];
    return rows.map((position) => {
      const livePrice = prices[position.ticker]?.price;
      const current_price =
        typeof livePrice === "number"
          ? livePrice
          : (position.current_price ?? null);
      const unrealized_pnl =
        typeof current_price === "number"
          ? (current_price - position.avg_cost) * position.quantity
          : (position.unrealized_pnl ?? null);
      const pnl_percent =
        typeof current_price === "number" && position.avg_cost > 0
          ? ((current_price - position.avg_cost) / position.avg_cost) * 100
          : (position.pnl_percent ?? null);
      return {
        ...position,
        current_price,
        unrealized_pnl,
        pnl_percent,
      };
    });
  }, [portfolio, prices]);

  return { portfolio, positions, history };
}
