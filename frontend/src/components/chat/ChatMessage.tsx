"use client";

// ChatMessage — one row in the chat history. User messages right-aligned with
// a subtle bg; assistant messages left-aligned plain text.
// Assistant messages with executed actions render inline TradeChip elements
// after the message body.

import clsx from "clsx";
import { TradeChipSuccess, TradeChipError } from "./TradeChip";
import type { StoredChatMessage } from "@/lib/types";

export default function ChatMessage({
  message,
}: {
  message: StoredChatMessage;
}) {
  const isUser = message.role === "user";
  return (
    <div
      className={clsx("flex flex-col", isUser ? "items-end" : "items-start")}
    >
      <div
        className={clsx(
          "max-w-[85%] rounded px-2 py-1.5 text-sm font-mono whitespace-pre-wrap",
          isUser
            ? "bg-bg-elevated text-text-primary"
            : "text-text-secondary",
        )}
      >
        {message.content}
      </div>
      {!isUser && message.actions && (
        <div className="mt-1 flex flex-wrap gap-1">
          {(message.actions.trades ?? []).map((t, i) => (
            <TradeChipSuccess key={`s-${i}`} trade={t} />
          ))}
          {(message.actions.errors ?? []).map((e, i) => (
            <TradeChipError key={`e-${i}`} err={e} />
          ))}
          {(message.actions.watchlist_changes ?? []).map((w, i) => (
            <span
              key={`w-${i}`}
              className="inline-flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded border border-accent/40 bg-accent/10 text-accent"
            >
              <span className="font-bold">{w.action.toUpperCase()}</span>
              <span>{w.ticker}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
