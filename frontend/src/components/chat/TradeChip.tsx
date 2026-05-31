"use client";

// TradeChip — compact inline pill rendered inside an assistant message.
// Two flavors: success (green border + text-price-up) for ExecutedTrade and
// error (red + text-price-down) for ChatTradeError.

import type { ExecutedTrade, ChatTradeError } from "@/lib/types";

export function TradeChipSuccess({ trade }: { trade: ExecutedTrade }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded border border-price-up/40 bg-price-up/10 text-price-up">
      <span className="font-bold">{trade.side.toUpperCase()}</span>
      <span>{trade.quantity}</span>
      <span>{trade.ticker}</span>
      <span className="text-text-secondary">@</span>
      <span>${trade.price.toFixed(2)}</span>
    </span>
  );
}

export function TradeChipError({ err }: { err: ChatTradeError }) {
  return (
    <span
      className="inline-flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded border border-price-down/40 bg-price-down/10 text-price-down"
      title={err.error}
    >
      <span className="font-bold">{err.side.toUpperCase()}</span>
      <span>{err.quantity}</span>
      <span>{err.ticker}</span>
      <span className="text-text-secondary">×</span>
      <span className="truncate max-w-[12rem]">{err.error}</span>
    </span>
  );
}
