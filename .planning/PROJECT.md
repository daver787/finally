# FinAlly — Finance Ally

## What This Is

FinAlly is an AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot — dark, data-dense, and visually stunning. This is the capstone project for an agentic AI coding course, built entirely by coding agents.

## Core Value

Users can watch prices stream live, trade a $10k simulated portfolio, and ask an AI to analyze their positions and execute trades for them — all in one dark, terminal-aesthetic interface accessible via a single Docker command.

## Requirements

### Validated

- ✓ Market data backend — simulator (GBM with correlated moves) + Massive API client, both behind shared `MarketDataSource` interface — existing
- ✓ In-memory price cache with version counter (thread-safe) — existing
- ✓ SSE streaming endpoint `/api/stream/prices` — pushes watchlist prices every 500ms — existing
- ✓ SQLite database with lazy initialization and seed data (10 default tickers, $10k cash) — existing
- ✓ All API routes: portfolio, watchlist, chat, health, SSE stream — existing
- ✓ Portfolio service: trade execution (market orders), P&L calculation, snapshot recording — existing
- ✓ Watchlist service: CRUD with price enrichment — existing
- ✓ LLM chat handler: portfolio context, LiteLLM → OpenRouter/Cerebras, structured output, auto-execution — existing
- ✓ Structured output schema: `ChatResponse` with `trades` and `watchlist_changes` — existing
- ✓ Backend test suite: 90 tests covering market data, portfolio, LLM, API routes — existing
- ✓ Dockerfile: multi-stage build (Node 20 → Python 3.12), serves frontend static export from FastAPI — Validated in Phase 4
- ✓ Start/stop scripts: macOS/Linux shell scripts + Windows PowerShell equivalents — Validated in Phase 4

### Active

- [ ] Frontend UI: Next.js TypeScript static export with dark terminal aesthetic
- [ ] Watchlist panel: ticker grid with live price flashing (green/red CSS animations), sparklines, click to select
- [ ] Main chart area: larger detail chart for selected ticker
- [ ] Portfolio heatmap: treemap of positions sized by weight, colored by P&L
- [ ] P&L chart: total portfolio value over time from portfolio_snapshots
- [ ] Positions table: ticker, qty, avg cost, current price, unrealized P&L, % change
- [ ] Trade bar: ticker + quantity input, buy/sell buttons, fractional shares, market orders
- [ ] AI chat panel: docked sidebar, message input, scrolling history, trade confirmations inline
- [ ] Header: live total portfolio value, cash balance, connection status indicator (green/yellow/red dot)
- [ ] E2E tests: Playwright suite covering fresh start, trading, chat, SSE resilience

### Out of Scope

- Real-time bidirectional WebSocket — SSE is sufficient for one-way price push
- Authentication/multi-user — single user, `user_id="default"` hardcoded
- Limit orders / order book — market orders only, dramatically simpler
- Mobile-native app — web-first, responsive but desktop-optimized
- Real money trading — simulated portfolio only, no brokerage API
- Video posts / social features — not applicable
- Cloud deploy (Terraform/App Runner) — stretch goal, not in core build

## Context

- **Capstone project** for an agentic AI coding course — the entire app is built by coding agents as a demonstration
- **Market data component is complete**: all backend routes, services, and market data subsystem are implemented and tested (90 tests passing)
- **Frontend directory is empty** (`frontend/`): Next.js has not been scaffolded yet — full implementation needed
- **No Dockerfile yet**: specified in PLAN.md but not implemented; multi-stage build needed
- **LiteLLM dependency not yet in pyproject.toml**: planned but `litellm` needs to be added before the chat route is fully functional
- **Color scheme**: Accent Yellow `#ecad0a`, Blue Primary `#209dd7`, Purple Secondary `#753991` (submit buttons)
- **Chart libraries**: Lightweight Charts or Recharts (canvas-based preferred for performance)
- **AI model**: `openrouter/openai/gpt-oss-120b` via OpenRouter with Cerebras inference provider

## Constraints

- **Tech Stack**: Python/FastAPI backend (uv), Next.js TypeScript frontend (static export), SQLite, SSE — no WebSockets, no separate DB server
- **Deployment**: Single Docker container on port 8000 — one command to run, no docker-compose for production
- **Single user**: No auth, `user_id="default"` throughout — simplicity over multi-tenancy
- **Market orders only**: No limit orders, no partial fills, instant fill at current price
- **LLM**: LiteLLM → OpenRouter → Cerebras (`openrouter/openai/gpt-oss-120b`) with structured outputs
- **Testing**: Backend unit tests in pytest; E2E in Playwright via `docker-compose.test.yml` in `test/`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SSE over WebSockets | One-way push is all we need; simpler, universal browser support | ✓ Good |
| Static Next.js export | Single origin, no CORS, one port, one container | — Pending |
| SQLite over Postgres | No multi-user = no need for DB server; zero config | ✓ Good |
| Single Docker container | Students run one command; no orchestration | — Pending |
| Market orders only | Eliminates order book complexity | ✓ Good |
| GBM simulator as default | Real data requires API key; simulator works out-of-the-box | ✓ Good |
| Auto-execute LLM trades | No confirmation needed (simulated money); creates fluid demo | — Pending |
| Structured LLM output | Reliable trade/watchlist extraction without string parsing | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-23 after initialization*
