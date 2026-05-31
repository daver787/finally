# Roadmap: FinAlly — AI Trading Workstation

## Overview

The backend is complete and tested (90 passing tests). The remaining work is a Next.js TypeScript frontend, a multi-stage Dockerfile, and Playwright E2E tests. Phases 1-2 build the live read-path UI on top of the existing SSE stream, Phase 3 adds the interactive mutation paths (trading and AI chat) plus the missing litellm dependency, Phase 4 packages everything into a single Docker container with start/stop scripts, and Phase 5 validates the complete system end-to-end with Playwright.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Frontend Foundation + Live Watchlist** - Scaffold Next.js static export, wire Zustand + SSE, build watchlist with price flashing and sparklines
- [x] **Phase 2: Charts + Portfolio Data** - Add Lightweight Charts price chart and P&L chart, Recharts treemap heatmap, and positions table (completed 2026-05-26)
- [x] **Phase 3: Trading + AI Chat** - Add trade bar with market orders, AI chat panel, and fix the missing litellm dependency (completed 2026-05-29)
- [x] **Phase 4: Docker + Start/Stop Scripts** - Multi-stage Dockerfile, FastAPI static mount, and platform start/stop scripts (completed 2026-05-29)
- [x] **Phase 5: E2E Tests** - Playwright test suite covering all key user scenarios via docker-compose (completed 2026-05-30)

## Phase Details

### Phase 1: Frontend Foundation + Live Watchlist

**Goal**: Users can open the app and see live prices streaming into a dark terminal-aesthetic watchlist with sparklines and price flash animations
**Mode:** mvp
**Depends on**: Nothing (backend already complete)
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04, WLIST-01, WLIST-02, WLIST-03, WLIST-04, WLIST-05, WLIST-06
**Success Criteria** (what must be TRUE):

  1. User opens `http://localhost:3000` (dev) and sees a dark terminal UI (#0d1117 background) with no login prompt
  2. Watchlist displays 10 default tickers with symbol, live price (2 decimal places), tick-over-tick change %, and a sparkline that fills in progressively from SSE data
  3. Price cells flash green on uptick and red on downtick with a ~500ms CSS fade animation that re-triggers on every price change
  4. Header shows live total portfolio value, cash balance, and a three-state connection dot (green/amber/red) that reflects SSE connection health
  5. User can add a new ticker to the watchlist and remove any existing ticker via the UI

**Plans:** 2/3 plans executed
**Wave 1**

- [x] 01-01-PLAN.md — Backend bootstrap: main.py, AppState, DB init + seed, health/watchlist/portfolio routes, mount SSE router, add python-dotenv

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Walking Skeleton: Next.js + Tailwind v4 + Zustand + useSSE hook + dark terminal layout shell with one live AAPL price

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 01-03-PLAN.md — Watchlist UI: Header (portfolio + cash + connection dot), WatchlistPanel + Row + Sparkline + useWatchlist hook (flash, add/remove, click-to-select)

**UI hint**: yes

### Phase 2: Charts + Portfolio Data

**Goal**: Users can click any ticker to see a detailed price chart, view their portfolio as a heatmap, track portfolio value over time, and see a full positions table
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: CHART-01, CHART-02, PORT-01, PORT-02
**Success Criteria** (what must be TRUE):

  1. Clicking a ticker in the watchlist renders a Lightweight Charts area/line chart for that ticker in the main chart area (no SSR crash during `next build`)
  2. The P&L chart displays total portfolio value over time sourced from `GET /api/portfolio/history` as a Lightweight Charts area chart
  3. The portfolio heatmap renders as a Recharts Treemap where each rectangle is sized by portfolio weight and colored green (profit) or red (loss)
  4. The positions table shows ticker, quantity, avg cost, current price, unrealized P&L, and % change for all open positions

**Plans:** 3/3 plans complete
**Wave 1**

- [x] 02-01-PLAN.md — Portfolio data plumbing: extend Zustand store + types + api.ts with portfolio + portfolioHistory; usePortfolio() hook fetches /api/portfolio and /api/portfolio/history with 10s interval and live-price enrichment
- [x] 02-02-PLAN.md — Price chart vertical slice: Lightweight Charts v5 area chart in center main slot, driven by useStore.selectedTicker + sparklines; next/dynamic ssr:false; replaces "Chart coming in Phase 2" placeholder

**Wave 2** *(blocked on 02-01)*

- [x] 02-03-PLAN.md — Portfolio panel vertical slice: Recharts Treemap heatmap + Lightweight Charts P&L chart + positions table in right aside; all dynamic ssr:false; replaces "Portfolio — Phase 2" placeholder; includes human-verify checkpoint

**UI hint**: yes

### Phase 3: Trading + AI Chat

**Goal**: Users can execute trades from the UI and chat with an AI assistant that can analyze their portfolio and execute trades on their behalf
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: TRADE-01, TRADE-02, TRADE-03, BKND-01, CHAT-01, CHAT-02, CHAT-03, CHAT-04
**Success Criteria** (what must be TRUE):

  1. `litellm` is present in `backend/pyproject.toml` and `uv sync` completes without error so the FastAPI process starts cleanly
  2. User can enter a ticker and fractional quantity, click BUY or SELL, and the trade executes immediately at current price with the portfolio updating inline — no confirmation dialog
  3. Inline success or error feedback appears after each trade and auto-dismisses after 3 seconds
  4. User can type a message in the chat panel and receive a full AI response; the input field is disabled and a loading indicator is visible while the response is pending
  5. When the AI executes a trade, an inline confirmation chip appears inside the assistant message showing ticker, side, quantity, and price

**Plans:** 4/4 plans complete
**Wave 1**

- [x] 03-01-PLAN.md — Backend trade slice: add litellm dep, portfolio service (execute_trade, build_portfolio_summary, record_snapshot), POST /api/portfolio/trade + GET / live valuation + GET /history routes, 30s snapshot loop + initial-snapshot in lifespan

**Wave 2** *(blocked on 03-01)*

- [x] 03-02-PLAN.md — Backend chat slice: llm/schema.py (ChatResponse + TradeAction + WatchlistChange), llm/chat.py (handle_chat — context build + LiteLLM acompletion + auto-execute + LLM_MOCK branch), routes/chat.py (POST /api/chat + GET /api/chat/history)
- [x] 03-03-PLAN.md — Frontend trade slice: lib/types.ts TradeResult, lib/api.ts postTrade, hooks/useTrade.ts, components/trade/TradeBar.tsx (BUY bg-primary / SELL bg-price-down / 3s auto-dismiss toast), TradingTerminal slot wiring

**Wave 3** *(blocked on 03-02 + 03-03)*

- [x] 03-04-PLAN.md — Frontend chat slice: lib/types chat family, lib/api postChat + fetchChatHistory, store chatOpen, hooks/useChat.ts, components/chat/{ChatPanel, ChatMessage, TradeChip}.tsx, Header.tsx Ask FinAlly toggle, TradingTerminal overlay

**UI hint**: yes

### Phase 4: Docker + Start/Stop Scripts

**Goal**: The complete application runs from a single `docker run` command and users have start/stop scripts for macOS and Windows
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: DOCK-01, DOCK-02, DOCK-03, SCPT-01, SCPT-02, SCPT-03
**Success Criteria** (what must be TRUE):

  1. `docker build -t finally .` succeeds: Node 20 stage runs `npm run build` producing a static export, Python 3.12 stage installs uv dependencies and copies the frontend output
  2. `docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally` starts the app; `http://localhost:8000` serves the full trading terminal with all API routes responding correctly (GET /api/health returns 200, GET /api/watchlist returns JSON — not HTML)
  3. SQLite data persists across container restarts via the named volume mount at `/app/db`
  4. `scripts/start_mac.sh` builds the image if absent and starts the container; `scripts/stop_mac.sh` stops it without removing the volume; PowerShell equivalents do the same on Windows

**Plans:** 3/3 plans complete
**Wave 1**

- [x] 04-01-PLAN.md — Multi-stage Dockerfile (Node 20 build -> Python 3.12 runtime, uv, non-root, HEALTHCHECK), .dockerignore, .env.example; main.py mount order verified; live-container human-verify APPROVED (completed 2026-05-29)
- [x] 04-02-PLAN.md — macOS/Linux start/stop scripts
- [x] 04-03-PLAN.md — Windows PowerShell start/stop scripts (human-verify APPROVED via Path B: pwsh 7.6.2 on macOS, completed 2026-05-29)

### Phase 5: E2E Tests

**Goal**: An automated Playwright suite validates all key user scenarios against the running Docker container, ensuring the full stack works end-to-end
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: E2E-01, E2E-02, E2E-03, E2E-04, E2E-05, E2E-06, E2E-07
**Success Criteria** (what must be TRUE):

  1. `test/docker-compose.test.yml` starts the app container (with healthcheck) and the Playwright container with `BASE_URL=http://app:8000`; tests wait for the app to be healthy before running
  2. Fresh-start test passes: default watchlist visible, $10k balance shown, prices are streaming (verified by price value change over time, not exact value assertions)
  3. Watchlist add/remove test passes: ticker added appears in the grid, removed ticker disappears
  4. Trade tests pass: buying shares causes cash balance to decrease and a new position row to appear; selling shares causes cash to increase and position quantity to update
  5. AI chat mock test passes (`LLM_MOCK=true`): sending a message receives the fixed mock response and a trade confirmation chip appears inline in the assistant message
  6. SSE resilience test passes: connection interrupted and automatic reconnection verified via connection status dot transitioning back to green

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Frontend Foundation + Live Watchlist | 2/3 | In Progress|  |
| 2. Charts + Portfolio Data | 3/3 | Complete   | 2026-05-26 |
| 3. Trading + AI Chat | 4/4 | Complete    | 2026-05-29 |
| 4. Docker + Start/Stop Scripts | 3/3 | Complete    | 2026-05-29 |
| 5. E2E Tests | 3/3 | Complete   | 2026-05-30 |
