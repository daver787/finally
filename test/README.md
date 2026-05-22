# FinAlly E2E Tests

Playwright end-to-end tests for the FinAlly AI Trading Workstation. These tests
drive the real app (FastAPI + Next.js static export) through a browser and
verify the core trading flows.

## Layout

```
test/
├── package.json            # Playwright dependency + scripts
├── playwright.config.ts    # Test runner config
├── docker-compose.test.yml # App container + Playwright container
├── e2e/
│   ├── helpers.ts          # Shared selectors / actions
│   └── trading.spec.ts     # 9 trading-terminal scenarios
└── README.md
```

## Scenarios covered

1. Fresh start — 10 default tickers, cash balance, prices streaming
2. Add and remove a ticker from the watchlist
3. Buy shares — cash decreases, position appears
4. Sell shares — cash increases, position quantity updates
5. Insufficient cash — validation error is shown
6. Portfolio heatmap renders with at least one position
7. P&L chart renders with data points
8. AI chat (mock mode) — send a message, see the response and the executed trade
9. SSE connection status indicator shows connected (green)

## Running the tests

### Via Docker (recommended — matches CI)

Builds the production image, starts the app, waits for it to be healthy, then
runs the suite in an official Playwright container.

```bash
cd test
docker-compose -f docker-compose.test.yml up --build \
  --exit-code-from playwright --abort-on-container-exit
```

The app runs with `LLM_MOCK=true` so the chat test is deterministic and needs
no API key.

### Locally against a running app

Start the app on `http://localhost:8000` first (Docker, or the start script),
then:

```bash
cd test
npm install
npx playwright install --with-deps chromium
npm test
```

Point at a different host with `BASE_URL`:

```bash
BASE_URL=http://localhost:3000 npm test
```

Useful variants:

```bash
npm run test:headed   # watch the browser
npm run test:ui       # Playwright UI mode
npm run report        # open the HTML report after a run
```

## Selector contract (`data-testid`)

The tests target stable `data-testid` attributes rather than CSS classes so
they survive styling changes. The frontend must expose:

| Area      | testid |
|-----------|--------|
| Header    | `cash-balance`, `total-value`, `connection-status` (+ `data-status`) |
| Watchlist | `watchlist`, `watchlist-row` (+ `data-ticker`), `watchlist-price`, `watchlist-add-input`, `watchlist-add-button`, `watchlist-remove-button` |
| Positions | `positions-table`, `position-row` (+ `data-ticker`), `position-qty` |
| Trade bar | `trade-ticker-input`, `trade-quantity-input`, `trade-buy-button`, `trade-sell-button`, `trade-feedback` |
| Charts    | `portfolio-heatmap`, `pnl-chart`, `main-chart` |
| AI chat   | `chat-toggle`, `chat-panel`, `chat-input`, `chat-send-button`, `chat-message` (+ `data-role`), `chat-loading`, `chat-trade-chip` |

Where reasonable, helpers fall back to text/role selectors if a testid is
missing.

## Notes

- Tests run serially (`workers: 1`) because they share one SQLite-backed
  portfolio; parallel runs would corrupt cash/position state.
- State-mutating tests are written to tolerate leftover state from prior runs
  (e.g. they assert `quantity >= 5` rather than exact equality after a buy).
- Each test retries once on failure (`retries: 1`) to absorb SSE timing jitter.
