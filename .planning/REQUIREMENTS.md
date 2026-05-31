# Requirements: FinAlly

**Defined:** 2026-05-23
**Core Value:** Users can watch live prices, trade a $10k simulated portfolio, and ask an AI to analyze and execute trades — all in one dark terminal-aesthetic interface via a single Docker command.

## v1 Requirements

### Core Frontend Infrastructure

- [ ] **CORE-01**: User sees dark terminal UI (bg #0d1117) on first load with no login required
- [ ] **CORE-02**: Single EventSource connection to `/api/stream/prices` feeds all components via Zustand store
- [ ] **CORE-03**: Connection status indicator in header shows green (live), amber (reconnecting), or red (disconnected)
- [ ] **CORE-04**: Header shows live total portfolio value and cash balance

### Watchlist

- [ ] **WLIST-01**: Watchlist grid shows 10 default tickers on load with symbol, price, tick-over-tick %, and sparkline
- [ ] **WLIST-02**: Price cells flash green on uptick / red on downtick with ~500ms CSS fade animation
- [ ] **WLIST-03**: Sparklines accumulate SSE price history from page load (custom SVG path, no library)
- [ ] **WLIST-04**: Clicking a ticker in the watchlist selects it in the main chart area
- [ ] **WLIST-05**: User can add a ticker to the watchlist
- [ ] **WLIST-06**: User can remove a ticker from the watchlist

### Charts

- [ ] **CHART-01**: Main chart area shows price-over-time for the selected ticker (Lightweight Charts v5, ssr:false)
- [ ] **CHART-02**: P&L chart shows total portfolio value over time from `/api/portfolio/history`

### Portfolio

- [ ] **PORT-01**: Portfolio heatmap (treemap) shows positions sized by portfolio weight, colored by unrealized P&L
- [ ] **PORT-02**: Positions table shows ticker, quantity, avg cost, current price, unrealized P&L, % change

### Trading

- [x] **TRADE-01**: Trade bar with ticker field, quantity input (fractional), buy button, and sell button
- [x] **TRADE-02**: Trades execute immediately at current price (market order, no confirmation dialog) and update portfolio
- [x] **TRADE-03**: Inline success/error feedback displayed after trade execution, auto-dismisses after 3 seconds

### AI Chat

- [x] **CHAT-01**: Chat panel is a docked sidebar with message input and scrolling conversation history
- [x] **CHAT-02**: User can send messages and receive AI assistant responses
- [x] **CHAT-03**: Trade executions from AI responses shown as inline confirmation chips in the assistant message
- [x] **CHAT-04**: Loading indicator while awaiting LLM response; input field disabled during pending state

### Backend Fix

- [x] **BKND-01**: `litellm` added to `backend/pyproject.toml` so the chat route starts without import error

### Docker & Deployment

- [x] **DOCK-01**: Multi-stage Dockerfile: Node 20 builds Next.js static export → Python 3.12 runtime image serves it
- [x] **DOCK-02**: FastAPI mounts static frontend and serves all API routes on port 8000 from a single container
- [x] **DOCK-03**: SQLite `db/` directory is volume-mounted for persistence across container restarts

### Scripts

- [x] **SCPT-01**: `scripts/start_mac.sh` — builds Docker image if needed, runs container with volume mount and `.env` file, prints URL
- [x] **SCPT-02**: `scripts/stop_mac.sh` — stops and removes container, preserves data volume
- [x] **SCPT-03**: `scripts/start_windows.ps1` and `scripts/stop_windows.ps1` — PowerShell equivalents of the above

### E2E Tests

- [ ] **E2E-01**: `test/docker-compose.test.yml` with app + Playwright containers, health check dependency, service-name networking (`http://app:8000`)
- [ ] **E2E-02**: Fresh start test: default watchlist visible, $10k balance shown, prices streaming
- [ ] **E2E-03**: Add and remove ticker from watchlist
- [ ] **E2E-04**: Buy shares: cash balance decreases, position appears in positions table
- [ ] **E2E-05**: Sell shares: cash balance increases, position quantity updates
- [ ] **E2E-06**: AI chat test (`LLM_MOCK=true`): message sent, response shown, trade execution chip appears inline
- [ ] **E2E-07**: SSE resilience: connection interrupted and automatic reconnection verified

## v2 Requirements

### Analytics
- **ANLYT-01**: Daily % change (requires previous-close data from Massive API)
- **ANLYT-02**: Volume data in watchlist (requires Massive API)
- **ANLYT-03**: OHLC candlestick chart (requires OHLC data, not available from simulator)

### Portfolio
- **PORT-03**: Portfolio performance benchmarking against S&P 500

### Auth / Multi-user
- **AUTH-01**: User accounts with login (enables multi-user)

### Deployment
- **DEPL-01**: Terraform configuration for AWS App Runner / Render cloud deployment

## Out of Scope

| Feature | Reason |
|---------|--------|
| Candlestick / OHLC chart | Simulator produces last-price only; fabricated OHLC would be misleading |
| Real-time WebSockets | SSE provides sufficient one-way push; bidirectional is unnecessary |
| Confirmation dialog for trades | Explicit design choice — simulated money, fluid demo UX |
| Limit orders / order book | Market orders only — eliminates order book complexity |
| Daily % change | No previous-close reference in simulator output |
| Authentication / login | Single-user hardcoded; no multi-tenancy needed |
| Mobile-native app | Web-first, desktop-optimized |
| Light theme | Doubles CSS surface area; contradicts brand identity |
| Multi-page routing | Single dense SPA; no routing needed |
| Cloud deployment (Terraform) | Stretch goal; not in core build |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Pending |
| CORE-02 | Phase 1 | Pending |
| CORE-03 | Phase 1 | Pending |
| CORE-04 | Phase 1 | Pending |
| WLIST-01 | Phase 1 | Pending |
| WLIST-02 | Phase 1 | Pending |
| WLIST-03 | Phase 1 | Pending |
| WLIST-04 | Phase 1 | Pending |
| WLIST-05 | Phase 1 | Pending |
| WLIST-06 | Phase 1 | Pending |
| CHART-01 | Phase 2 | Pending |
| CHART-02 | Phase 2 | Pending |
| PORT-01 | Phase 2 | Pending |
| PORT-02 | Phase 2 | Pending |
| TRADE-01 | Phase 3 | Complete |
| TRADE-02 | Phase 3 | Complete |
| TRADE-03 | Phase 3 | Complete |
| BKND-01 | Phase 3 | Complete |
| CHAT-01 | Phase 3 | Complete |
| CHAT-02 | Phase 3 | Complete |
| CHAT-03 | Phase 3 | Complete |
| CHAT-04 | Phase 3 | Complete |
| DOCK-01 | Phase 4 | Complete |
| DOCK-02 | Phase 4 | Complete |
| DOCK-03 | Phase 4 | Complete |
| SCPT-01 | Phase 4 | Complete |
| SCPT-02 | Phase 4 | Complete |
| SCPT-03 | Phase 4 | Complete |
| E2E-01 | Phase 5 | Pending |
| E2E-02 | Phase 5 | Pending |
| E2E-03 | Phase 5 | Pending |
| E2E-04 | Phase 5 | Pending |
| E2E-05 | Phase 5 | Pending |
| E2E-06 | Phase 5 | Pending |
| E2E-07 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 35 total
- Mapped to phases: 35
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-23*
*Last updated: 2026-05-23 after initial definition*
