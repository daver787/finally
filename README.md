# FinAlly — AI Trading Workstation

An AI-powered trading terminal that streams live market data, lets you trade a simulated portfolio, and includes an LLM assistant that can analyze positions and execute trades on your behalf.

![Dark terminal aesthetic with live prices, portfolio heatmap, and AI chat]

## Quick Start

```bash
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env
./scripts/start_mac.sh        # macOS/Linux
# or: .\scripts\start_windows.ps1  (Windows PowerShell)
```

Open **http://localhost:8000** — no login required.

## What You Get

- **Live price stream** — 10 default tickers updating every ~500ms with green/red flash animations
- **Sparkline charts** — mini price charts that fill in progressively from the SSE stream
- **Simulated trading** — $10,000 virtual cash, instant market order fills, no fees
- **Portfolio heatmap** — treemap sized by position weight, colored by P&L
- **AI chat assistant** — ask questions, get analysis, and have trades executed via natural language

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter key for LLM chat |
| `MASSIVE_API_KEY` | No | Real market data (simulator used if absent) |
| `LLM_MOCK` | No | Set `true` for deterministic mock responses (testing) |

Copy `.env.example` to `.env` and fill in your keys.

## Architecture

Single Docker container on port 8000:

- **Frontend**: Next.js + TypeScript, built as a static export, served by FastAPI
- **Backend**: FastAPI (Python/uv) — REST API, SSE streaming, LLM integration
- **Database**: SQLite (auto-initialized with seed data on first run)
- **Real-time**: Server-Sent Events for price streaming
- **AI**: LiteLLM → OpenRouter (Cerebras) with structured outputs for trade execution

## Development

```bash
# Backend
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

## Testing

```bash
cd test && docker compose -f docker-compose.test.yml up --abort-on-container-exit
```

E2E tests use Playwright with `LLM_MOCK=true` for speed and determinism.

## Scripts

| Script | Description |
|---|---|
| `scripts/start_mac.sh` | Build image (if needed) and start container |
| `scripts/stop_mac.sh` | Stop container (preserves database volume) |
| `scripts/start_windows.ps1` | Windows PowerShell equivalent |
| `scripts/stop_windows.ps1` | Windows PowerShell equivalent |

Pass `--build` to force a rebuild: `./scripts/start_mac.sh --build`
