"use client";

// TradeBar — market-order entry. Instant fill, no confirmation dialog.

import { useEffect, useState } from "react";
import type { TradeSide } from "@/lib/types";

interface TradeBarProps {
  defaultTicker: string | null;
  onTrade: (ticker: string, quantity: number, side: TradeSide) => Promise<void>;
}

type Feedback = { kind: "ok" | "err"; text: string } | null;

export function TradeBar({ defaultTicker, onTrade }: TradeBarProps) {
  const [ticker, setTicker] = useState(defaultTicker ?? "");
  const [qty, setQty] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [touched, setTouched] = useState(false);

  // Follow the selected watchlist symbol until the user edits the field.
  useEffect(() => {
    if (!touched && defaultTicker) setTicker(defaultTicker);
  }, [defaultTicker, touched]);

  const submit = async (side: TradeSide) => {
    const sym = ticker.trim().toUpperCase();
    const quantity = parseFloat(qty);
    if (!sym) {
      setFeedback({ kind: "err", text: "Enter a ticker symbol" });
      return;
    }
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setFeedback({ kind: "err", text: "Enter a positive quantity" });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      await onTrade(sym, quantity, side);
      setFeedback({
        kind: "ok",
        text: `${side === "buy" ? "Bought" : "Sold"} ${quantity} ${sym}`,
      });
      setQty("");
    } catch (e) {
      setFeedback({
        kind: "err",
        text: e instanceof Error ? e.message : "Trade failed",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel panel-in shrink-0">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <span
          className="panel-title shrink-0"
          style={{ paddingRight: 4 }}
        >
          Order
        </span>

        <input
          data-testid="trade-ticker-input"
          value={ticker}
          onChange={(e) => {
            setTicker(e.target.value.toUpperCase());
            setTouched(true);
          }}
          placeholder="TICKER"
          aria-label="Ticker"
          className="field px-2.5 py-1.5 text-xs uppercase tracking-wide"
          style={{ width: 92 }}
          disabled={busy}
        />

        <input
          data-testid="trade-quantity-input"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          placeholder="QTY"
          aria-label="Quantity"
          type="number"
          step="any"
          min="0"
          inputMode="decimal"
          className="field px-2.5 py-1.5 text-xs tnum"
          style={{ width: 90 }}
          disabled={busy}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit("buy");
          }}
        />

        <button
          data-testid="trade-buy-button"
          onClick={() => submit("buy")}
          disabled={busy}
          className="btn px-4 py-1.5 text-xs"
          style={{ background: "var(--blue)", color: "#06121a" }}
        >
          BUY
        </button>
        <button
          data-testid="trade-sell-button"
          onClick={() => submit("sell")}
          disabled={busy}
          className="btn px-4 py-1.5 text-xs"
          style={{ background: "var(--down)", color: "#1a0608" }}
        >
          SELL
        </button>

        <div className="flex items-center gap-2 ml-1 min-h-[18px] flex-1">
          {busy && <div className="spinner" />}
          <span
            data-testid="trade-feedback"
            data-kind={feedback?.kind ?? ""}
            className="text-[11px] tnum"
            style={{
              color:
                feedback?.kind === "ok"
                  ? "var(--up)"
                  : feedback?.kind === "err"
                    ? "var(--down)"
                    : "var(--ink-faint)",
            }}
          >
            {feedback
              ? `${feedback.kind === "ok" ? "✓ " : "✕ "}${feedback.text}`
              : ""}
          </span>
          {!busy && !feedback && (
            <span
              className="text-[10px] tracking-wide"
              style={{ color: "var(--ink-faint)" }}
            >
              Market order · instant fill · fractional shares OK
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
