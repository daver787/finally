"use client";

// ChatPanel — collapsible AI copilot sidebar. Sends messages to /api/chat
// and renders executed trades / watchlist changes as inline confirmation chips.

import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@/lib/types";
import { fmtPrice, fmtQty } from "@/lib/format";

interface ChatPanelProps {
  open: boolean;
  messages: ChatMessage[];
  busy: boolean;
  onSend: (text: string) => void;
  onClose: () => void;
}

const PROMPTS = [
  "Analyze my portfolio risk",
  "Buy 5 shares of NVDA",
  "What should I sell?",
];

export function ChatPanel({
  open,
  messages,
  busy,
  onSend,
  onClose,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, busy]);

  const send = () => {
    const text = draft.trim();
    if (!text || busy) return;
    onSend(text);
    setDraft("");
  };

  return (
    <aside
      data-testid="chat-panel"
      className="flex flex-col shrink-0 panel-in"
      style={{
        width: 360,
        background: "var(--bg-panel)",
        borderLeft: "1px solid var(--border)",
        display: open ? "flex" : "none",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3.5 h-12 shrink-0"
        style={{
          borderBottom: "1px solid var(--border)",
          background:
            "linear-gradient(180deg, rgba(117,57,145,0.16), transparent)",
        }}
      >
        <div className="flex items-center gap-2">
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: 999,
              background: "var(--accent)",
              display: "inline-block",
              boxShadow: "0 0 8px var(--accent)",
            }}
          />
          <span className="text-xs font-bold tracking-[0.12em] uppercase">
            FinAlly Copilot
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-base leading-none"
          style={{ color: "var(--ink-faint)" }}
          aria-label="Close chat"
        >
          ×
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="pt-6 text-center">
            <div
              className="text-xs mb-3"
              style={{ color: "var(--ink-dim)" }}
            >
              Ask FinAlly to analyze your portfolio or execute trades.
            </div>
            <div className="flex flex-col gap-1.5">
              {PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => onSend(p)}
                  className="text-[11px] px-2.5 py-1.5 rounded text-left"
                  style={{
                    background: "var(--bg-panel-2)",
                    border: "1px solid var(--border)",
                    color: "var(--ink-dim)",
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}

        {busy && (
          <div className="flex items-center gap-2 msg-in">
            <div className="spinner" />
            <span
              className="text-[11px] tracking-wide"
              style={{ color: "var(--ink-faint)" }}
            >
              FinAlly is thinking…
            </span>
          </div>
        )}
      </div>

      {/* Composer */}
      <div
        className="p-2.5 shrink-0"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        <div className="flex items-end gap-2">
          <textarea
            data-testid="chat-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Message FinAlly…"
            rows={2}
            className="field flex-1 px-2.5 py-2 text-xs resize-none"
            style={{ fontFamily: "var(--font-display)" }}
            disabled={busy}
          />
          <button
            data-testid="chat-send-button"
            onClick={send}
            disabled={busy || !draft.trim()}
            className="btn px-3.5 py-2 text-xs"
            style={{ background: "var(--purple)", color: "var(--ink)" }}
          >
            SEND
          </button>
        </div>
      </div>
    </aside>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`msg-in flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        data-testid="chat-message"
        data-role={message.role}
        className="max-w-[88%] px-3 py-2 text-xs leading-relaxed rounded"
        style={{
          background: isUser ? "var(--bg-elevated)" : "var(--bg-panel-2)",
          border: `1px solid ${isUser ? "var(--border-bright)" : "var(--border)"}`,
          borderLeft: isUser
            ? "1px solid var(--border-bright)"
            : "2px solid var(--accent)",
          color: "var(--ink)",
          whiteSpace: "pre-wrap",
        }}
      >
        <div>{message.content}</div>

        {message.trades && message.trades.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {message.trades.map((t, i) => (
              <span
                key={i}
                data-testid="chat-trade-chip"
                className="tnum text-[10px] px-1.5 py-0.5 rounded"
                style={{
                  background:
                    t.side === "buy"
                      ? "rgba(32,157,215,0.16)"
                      : "rgba(255,77,94,0.16)",
                  border: `1px solid ${t.side === "buy" ? "var(--blue)" : "var(--down)"}`,
                  color: t.side === "buy" ? "#7fd3f0" : "#ffb3ba",
                }}
              >
                ✓ {t.side === "buy" ? "Bought" : "Sold"} {fmtQty(t.quantity)}{" "}
                {t.ticker}
                {t.price ? ` @ $${fmtPrice(t.price)}` : ""}
              </span>
            ))}
          </div>
        )}

        {message.watchlistChanges && message.watchlistChanges.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {message.watchlistChanges.map((w, i) => (
              <span
                key={i}
                className="tnum text-[10px] px-1.5 py-0.5 rounded"
                style={{
                  background: "rgba(236,173,10,0.14)",
                  border: "1px solid var(--accent)",
                  color: "#f3cf6e",
                }}
              >
                {w.action === "add" ? "+ Watch" : "− Unwatch"} {w.ticker}
              </span>
            ))}
          </div>
        )}

        {message.errors && message.errors.length > 0 && (
          <div className="flex flex-col gap-1 mt-1.5">
            {message.errors.map((err, i) => (
              <span
                key={i}
                className="text-[10px]"
                style={{ color: "var(--down)" }}
              >
                ✕ {err}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
