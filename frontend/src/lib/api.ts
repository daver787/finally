// Typed REST wrappers. All calls go to the same origin: in dev Next.js's
// rewrites() forwards /api/* to uvicorn on :8000; in Phase 4 the static
// bundle is served directly by FastAPI so the proxy is unneeded.
//
// BASE honours NEXT_PUBLIC_API_BASE (Phase 2 critical constraint #6) for
// dev/prod parity. In Next dev mode the value is "" and rewrites in
// next.config.ts handle proxying; in production the static bundle is served
// by FastAPI on the same origin so "" is also correct.

import type {
  PortfolioSummary,
  PortfolioHistoryPoint,
  TradeResult,
  ChatReply,
  StoredChatMessage,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function fetchPortfolio(): Promise<PortfolioSummary> {
  const r = await fetch(`${BASE}/api/portfolio`);
  if (!r.ok) {
    throw new Error(`fetchPortfolio: ${r.status}`);
  }
  return r.json().catch(() => { throw new Error("fetchPortfolio: malformed JSON"); });
}

// Returns the portfolio_snapshots history series for the P&L chart.
// The /api/portfolio/history backend route is not yet implemented — any
// non-OK response (404, 5xx, network) is absorbed as an empty array. This is
// the contract callers depend on: the empty array degrades the UI cleanly
// until Phase 3 ships trades + snapshot writes, with no consumer-side
// branching required. Do NOT add console.error here — the empty array is the
// contract, not an error condition (per threat T-02-01).
export async function fetchPortfolioHistory(): Promise<PortfolioHistoryPoint[]> {
  const r = await fetch(`${BASE}/api/portfolio/history`);
  if (!r.ok) return [];
  return r.json().catch(() => []);
}

// POST /api/portfolio/trade. Returns { ok, ... } discriminated union — never
// throws on 4xx (returns ok:false), only throws on network failure (caller
// handles). 422 ValidationError detail arrays are flattened to a short
// human-readable string so the UI toast has something useful to render.
export async function postTrade(
  payload: { ticker: string; side: "buy" | "sell"; quantity: number },
): Promise<TradeResult> {
  const r = await fetch(`${BASE}/api/portfolio/trade`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (r.ok) {
    const body = await r.json();
    return {
      ok: true,
      price: body.price,
      cash_balance: body.cash_balance,
      total_value: body.total_value,
    };
  }
  const body = await r.json().catch(() => ({}));
  let error: string;
  if (typeof body.detail === "string") {
    error = body.detail;
  } else if (Array.isArray(body.detail)) {
    // FastAPI 422 ValidationError shape: [{loc, msg, type, ...}]
    error = body.detail
      .slice(0, 2)
      .map((d: { msg?: string }) => d.msg ?? "invalid input")
      .join(", ");
  } else {
    error = `HTTP ${r.status}`;
  }
  return { ok: false, error };
}

// Phase 3 chat helpers. postChat throws on non-OK (caller surfaces error in
// the panel). fetchChatHistory absorbs errors to [] so a stale backend doesn't
// blank the panel.
export async function postChat(content: string): Promise<ChatReply> {
  const r = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    let msg: string;
    if (typeof body.detail === "string") {
      msg = body.detail;
    } else if (Array.isArray(body.detail)) {
      msg = body.detail
        .slice(0, 2)
        .map((d: { msg?: string }) => d.msg ?? "invalid input")
        .join(", ");
    } else {
      msg = "request failed";
    }
    throw new Error(`postChat: ${r.status} ${msg}`);
  }
  return (await r.json()) as ChatReply;
}

export async function fetchChatHistory(): Promise<StoredChatMessage[]> {
  const r = await fetch(`${BASE}/api/chat/history`);
  if (!r.ok) return [];
  return r.json().catch(() => []);
}
