// Shared TypeScript interfaces for FinAlly.
//
// Field names are snake_case to mirror backend JSON exactly (see
// backend/app/market/models.py PriceUpdate.to_dict()). Do not camelCase —
// we trade a tiny bit of TS convention to avoid a serialization layer.

export interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number; // Unix seconds (float)
  change: number;
  change_percent: number;
  direction: "up" | "down" | "flat";
}

export interface WatchlistEntry {
  id: string;
  ticker: string;
  added_at: string;
  price: number | null;
  previous_price: number | null;
  change_percent: number | null;
  direction: "up" | "down" | "flat" | null;
}

export interface PositionEntry {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  pnl_percent: number | null;
}

export interface PortfolioSummary {
  cash_balance: number;
  total_value: number;
  positions: PositionEntry[];
}

// One row from /api/portfolio/history. Snake_case mirrors the
// portfolio_snapshots SQLite table columns (total_value REAL, recorded_at TEXT
// ISO timestamp). The /history backend route is not yet implemented — the api
// wrapper in lib/api.ts therefore degrades non-OK responses to an empty array.
export interface PortfolioHistoryPoint {
  total_value: number;
  recorded_at: string;
}

// ─── Phase 3: trading + chat additions ───

// TradeResult is the discriminated return from postTrade(). Snake_case
// mirrors the backend POST /api/portfolio/trade response shape (price,
// cash_balance, total_value). On a 4xx response the wrapper sets ok=false
// and surfaces the backend's `detail` (or a derived 422 summary) via
// `error`, so the UI can render the message in a toast without throwing.
// Network failures still throw out of postTrade — caller handles those.
export interface TradeResult {
  ok: boolean;
  price?: number;
  cash_balance?: number;
  total_value?: number;
  error?: string;
}

// Chat type family — snake_case mirrors backend POST /api/chat and
// GET /api/chat/history shapes exactly (no transformation layer). The
// distinct `ChatTradeError` name disambiguates the frontend type from the
// backend `TradeError` exception concept used in services/portfolio.py.

export interface ExecutedTrade {
  ticker: string;
  side: string;
  quantity: number;
  price: number;
}

export interface ChatTradeError {
  ticker: string;
  side: string;
  quantity: number;
  error: string;
}

export interface ChatWatchlistChange {
  ticker: string;
  action: "add" | "remove";
}

export interface ChatExecuted {
  trades: ExecutedTrade[];
  errors: ChatTradeError[];
  watchlist_changes: ChatWatchlistChange[];
}

export interface ChatReply {
  message: string;
  executed_actions: ChatExecuted;
}

export interface StoredChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions: ChatExecuted | null;
  created_at: string;
}
