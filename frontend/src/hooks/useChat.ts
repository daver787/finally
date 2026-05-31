"use client";

// useChat — local-state message list + send() + pending flag.
// Hydrates from /api/chat/history once on mount (no polling — chat is
// request/response).
// After send(): optimistic user-message append → POST /api/chat → append
// assistant message.
// If executed_actions.trades non-empty, refresh portfolio via
// useStore.getState() (same pattern as useTrade).

import { useEffect, useState } from "react";
import { useStore } from "@/store";
import {
  postChat,
  fetchChatHistory,
  fetchPortfolio,
  fetchPortfolioHistory,
} from "@/lib/api";
import type { StoredChatMessage } from "@/lib/types";

export function useChat(): {
  messages: StoredChatMessage[];
  send: (text: string) => Promise<void>;
  pending: boolean;
} {
  const [messages, setMessages] = useState<StoredChatMessage[]>([]);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchChatHistory()
      .then((history) => {
        if (!cancelled) setMessages(history);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  async function send(text: string): Promise<void> {
    if (pending) return;
    const optimisticUser: StoredChatMessage = {
      id: `pending-${Date.now()}`,
      role: "user",
      content: text,
      actions: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser]);
    setPending(true);
    try {
      const reply = await postChat(text);
      const assistantMsg: StoredChatMessage = {
        id: `pending-${Date.now()}-a`,
        role: "assistant",
        content: reply.message,
        actions: reply.executed_actions,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      if (
        reply.executed_actions.trades.length > 0 ||
        reply.executed_actions.watchlist_changes.length > 0
      ) {
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
          // Swallow refresh errors — the chat reply already rendered;
          // the next usePortfolio() poll will reconcile within 10s.
          console.error("useChat: post-chat portfolio refresh failed", err);
        }
      }
    } catch (err) {
      const errorMsg: StoredChatMessage = {
        id: `pending-${Date.now()}-e`,
        role: "assistant",
        content: `Error: ${
          err instanceof Error
            ? err.message
            : "Could not reach the assistant. Please try again."
        }`,
        actions: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setPending(false);
    }
  }

  return { messages, send, pending };
}
