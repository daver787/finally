# FinAlly Project - the Finance Ally

All project documentation is in the `planning` directory.

The key document is PLAN.md included in full below; the market data component has been completed and is summarized in the file `planning/MARKET_DATA_SUMMARY.md` with more details in the `planning/archive` folder. Consult these docs only when required. The remainder of the platform is still to be developed.

@planning/PLAN.md

<!-- GSD:project-start source:PROJECT.md -->
## Project

**FinAlly — Finance Ally**

FinAlly is an AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot — dark, data-dense, and visually stunning. This is the capstone project for an agentic AI coding course, built entirely by coding agents.

**Core Value:** Users can watch prices stream live, trade a $10k simulated portfolio, and ask an AI to analyze their positions and execute trades for them — all in one dark, terminal-aesthetic interface accessible via a single Docker command.

### Constraints

- **Tech Stack**: Python/FastAPI backend (uv), Next.js TypeScript frontend (static export), SQLite, SSE — no WebSockets, no separate DB server
- **Deployment**: Single Docker container on port 8000 — one command to run, no docker-compose for production
- **Single user**: No auth, `user_id="default"` throughout — simplicity over multi-tenancy
- **Market orders only**: No limit orders, no partial fills, instant fill at current price
- **LLM**: LiteLLM → OpenRouter → Cerebras (`openrouter/openai/gpt-oss-120b`) with structured outputs
- **Testing**: Backend unit tests in pytest; E2E in Playwright via `docker-compose.test.yml` in `test/`
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12+ - Backend API, market data, LLM integration (all of `backend/`)
- TypeScript - Frontend application (planned in `frontend/`, not yet implemented)
- SQL (SQLite dialect) - Database schema and queries (planned in `backend/db/`)
## Runtime
- Python 3.12 (minimum), currently running Python 3.14 in `.venv` (see `backend/.venv/lib/python3.14/`)
- asyncio event loop — all I/O is async, no threading except `PriceCache` lock (`backend/app/market/cache.py`)
- uv (modern Python package manager)
- Lockfile: `backend/uv.lock` — present and committed (813 lines, revision 3)
## Frameworks
- FastAPI 0.128.7 - HTTP API framework, SSE streaming, static file serving
- Starlette (transitive via FastAPI) - ASGI foundation, `StreamingResponse`
- Uvicorn 0.40.0 (with `[standard]` extras) - ASGI server
- Pydantic 2.12.5 - Data validation and structured output schemas
- pytest 9.0.2 - Test runner (`backend/tests/`)
- pytest-asyncio 0.24.0 - Async test support (`asyncio_mode = "auto"`)
- pytest-cov 5.0.0 - Coverage measurement
- ruff 0.15.0 - Linting and formatting (`line-length = 100`, Python 3.12 target)
- hatchling - Build backend for the uv project
- Next.js with TypeScript, `output: 'export'` static mode
- Tailwind CSS
- Lightweight Charts or Recharts for canvas-based charts
## Key Dependencies
- `fastapi>=0.115.0` (`backend/pyproject.toml`) - Core web framework
- `uvicorn[standard]>=0.32.0` (`backend/pyproject.toml`) - ASGI server with production extras
- `massive==2.2.0` (`backend/uv.lock`) - Polygon.io REST API client; used by `MassiveDataSource` in `backend/app/market/massive_client.py`
- `numpy>=2.0.0` / 2.4.2 (`backend/uv.lock`) - GBM simulator math (Cholesky decomposition for correlated price moves in `backend/app/market/simulator.py`)
- `pydantic 2.12.5` - Structured output schema for LLM responses (planned in `backend/app/llm/`)
- `python-dotenv 1.2.1` - `.env` file loading (present in lock, not yet used in app source — needed once FastAPI app entrypoint is built)
- `rich 14.3.2` - Terminal rendering; used in demo (`backend/market_data_demo.py`) and dev tooling
- `certifi`, `urllib3` - HTTP transport for `massive` client
- `litellm` - LLM calls via OpenRouter/Cerebras (cerebras-inference skill: `.claude/skills/cerebras/SKILL.md`)
- Playwright - E2E testing (partially present in `test/node_modules/`)
## Configuration
- `.env` file at project root (gitignored); `.env` is loaded by the running container
- Required variables:
- `backend/pyproject.toml` — Python project definition, pytest config, ruff config, coverage config
- `backend/uv.lock` — Pinned dependency lockfile (committed)
## Platform Requirements
- Python 3.12+
- `uv` installed globally
- `uv sync --extra dev` to install all dependencies including test/lint tools
- Single Docker container, port 8000
- SQLite database at `/app/db/finally.db` (volume-mounted for persistence)
- `uvicorn` serves FastAPI on port 8000
- Multi-stage Docker build: Node 20 (frontend build) → Python 3.12 slim (runtime)
- No Dockerfile exists in the repository yet — it is specified in the project plan (`CLAUDE.md`) but not yet implemented
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Snake_case for all Python source files: `cache.py`, `massive_client.py`, `seed_prices.py`
- Module-per-concept, not per-class: one concept per file (e.g., `models.py` owns `PriceUpdate`, `interface.py` owns `MarketDataSource`)
- Test files prefixed with `test_`: `test_cache.py`, `test_simulator.py`, `test_stream.py`
- Factory functions get their own file: `factory.py`
- PascalCase: `PriceCache`, `GBMSimulator`, `MassiveDataSource`, `SimulatorDataSource`
- Abstract base classes named as the concept (not prefixed with `Abstract` or `Base`): `MarketDataSource`
- Concrete implementations named `<Provider>DataSource`: `SimulatorDataSource`, `MassiveDataSource`
- Snake_case for all functions and methods: `create_market_data_source`, `get_price`, `rebuild_cholesky`
- Private methods prefixed with single underscore: `_poll_once`, `_fetch_snapshots`, `_run_loop`, `_rebuild_cholesky`, `_add_ticker_internal`
- Factory functions named `create_<thing>`: `create_market_data_source`, `create_stream_router`
- Async methods for I/O-bound operations: `start`, `stop`, `add_ticker`, `remove_ticker`, `_poll_once`
- Sync methods for pure computation: `step`, `get_price`, `get_tickers`, `_pairwise_correlation`
- Snake_case throughout: `price_cache`, `poll_interval`, `update_interval`, `api_key`
- Constant-style (uppercase with underscores) for module-level constants: `SEED_PRICES`, `TICKER_PARAMS`, `DEFAULT_PARAMS`, `CORRELATION_GROUPS`, `INTRA_TECH_CORR`, `TRADING_SECONDS_PER_YEAR`
- Private instance attributes prefixed with `_`: `self._cache`, `self._tickers`, `self._task`, `self._client`
- All type annotations use Python 3.12+ syntax with `from __future__ import annotations`
- Union types use `X | Y` syntax (not `Union[X, Y]`): `float | None`, `asyncio.Task | None`
- Collections annotated with built-in generics: `list[str]`, `dict[str, float]`
## Code Style
- Tool: `ruff` (configured in `backend/pyproject.toml`)
- Line length: 100 characters (`line-length = 100`)
- Target version: Python 3.12 (`target-version = "py312"`)
- Line-too-long rule (`E501`) intentionally ignored — formatter handles wrapping
- `ruff` with rule sets: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `N` (naming), `W` (warnings)
- Run with: `uv run --extra dev ruff check app/ tests/`
## Import Organization
## Error Handling
## Logging
- `logger.info()` — lifecycle events: start/stop, ticker add/remove
- `logger.debug()` — high-frequency events: individual GBM random shocks, poll counts
- `logger.warning()` — recoverable data issues: missing price for a ticker
- `logger.error()` — external API failures: poll failures
- `logger.exception()` — unexpected exceptions in hot paths (includes traceback)
## Comments
- Module-level docstrings on every file explaining purpose
- Class docstrings explaining the abstraction, its role, and usage lifecycle
- Method docstrings for public methods explaining behavior, not just re-stating the name
- Inline comments for non-obvious math (GBM formula constants, Cholesky math)
- Comments explaining WHY a decision was made, not what the code does:
## Function Design
- Prefer keyword-argument-friendly parameter names
- `__init__` parameters mirror instance attribute names without the underscore: `price_cache` → `self._cache`, `api_key` → `self._api_key`
- Default values for optional config params: `update_interval: float = 0.5`, `poll_interval: float = 15.0`
- Prefer `X | None` over raising exceptions for "not found" scenarios: `get_price()` returns `float | None`
- Factory functions always return the abstract interface type, not a concrete type: `-> MarketDataSource`
- Methods that modify state (`update()`) return the created object for caller convenience
## Module Design
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
```
## Component Responsibilities
| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app factory | Wire routes, lifespan tasks, static file mount | `backend/app/main.py` |
| AppState | Process-wide singletons: PriceCache, MarketDataSource, db_path | `backend/app/state.py` |
| MarketDataSource | Abstract interface for price producers | `backend/app/market/interface.py` |
| SimulatorDataSource | GBM-based price simulation, asyncio background task | `backend/app/market/simulator.py` |
| MassiveDataSource | Polygon.io REST polling, asyncio background task | `backend/app/market/massive_client.py` |
| PriceCache | Thread-safe in-memory price store with version counter | `backend/app/market/cache.py` |
| PriceUpdate | Immutable price snapshot dataclass with computed properties | `backend/app/market/models.py` |
| create_market_data_source | Factory: selects simulator or Massive based on MASSIVE_API_KEY | `backend/app/market/factory.py` |
| stream router | SSE endpoint — pushes watchlist prices every 500ms | `backend/app/routes/stream.py` |
| portfolio routes | GET /portfolio, POST /portfolio/trade, GET /portfolio/history | `backend/app/routes/portfolio.py` |
| watchlist routes | GET/POST /watchlist, DELETE /watchlist/{ticker} | `backend/app/routes/watchlist.py` |
| chat route | POST /api/chat — delegates to LLM handler | `backend/app/routes/chat.py` |
| health route | GET /api/health — liveness probe | `backend/app/routes/health.py` |
| portfolio service | Trade execution, P&L calculation, snapshot recording | `backend/app/services/portfolio.py` |
| watchlist service | DB CRUD for watchlist, price enrichment | `backend/app/services/watchlist.py` |
| LLM chat handler | Portfolio context build, LiteLLM call, trade auto-execution | `backend/app/llm/chat.py` |
| LLM schema | Pydantic structured-output models (ChatResponse, TradeAction) | `backend/app/llm/schema.py` |
| DB init | Lazy schema creation + seed data on first use | `backend/app/db/init_db.py` |
| DB schema | SQL DDL strings, table definitions, default constants | `backend/app/db/schema.py` |
| Next.js SPA | Full trading UI — compiled static export committed to repo | `backend/static/` |
| seed prices | GBM starting prices and per-ticker volatility params | `backend/app/market/seed_prices.py` |
## Pattern Overview
- Single process, single port (8000). No inter-service communication.
- FastAPI serves both the REST/SSE API and the Next.js static export under one origin (no CORS).
- Market data producers (simulator or Massive) write to a shared `PriceCache`; all consumers read from the cache — no direct coupling to the data source.
- Strategy Pattern: `MarketDataSource` abstract class with two interchangeable implementations selected at startup via factory.
- Dependency injection via FastAPI `Depends()` — routes receive a fresh SQLite connection and shared cache per request.
- Async background tasks (asyncio): market data loop + portfolio snapshot loop, both managed inside the FastAPI lifespan context manager.
## Layers
- Purpose: HTTP request parsing, response shaping, error translation
- Location: `backend/app/routes/`
- Contains: FastAPI `APIRouter` modules, Pydantic request/response models
- Depends on: Services layer, AppState dependencies
- Used by: FastAPI app in `main.py`
- Purpose: Business logic — trade execution, P&L math, portfolio valuation, watchlist CRUD
- Location: `backend/app/services/`
- Contains: Framework-agnostic functions operating on `sqlite3.Connection` and `PriceCache`
- Depends on: DB layer, market cache
- Used by: Routes layer and LLM chat handler (shared trade path)
- Purpose: Conversational AI — portfolio context building, LiteLLM call, response parsing, auto-trade execution
- Location: `backend/app/llm/`
- Contains: `chat.py` (handler), `schema.py` (Pydantic structured output models)
- Depends on: Services layer, PriceCache, DB layer
- Used by: `routes/chat.py`
- Purpose: Produce live prices into the shared PriceCache
- Location: `backend/app/market/`
- Contains: Abstract interface, two concrete implementations, cache, models, SSE stream, seed data
- Depends on: Nothing from the rest of the app (pure data producer)
- Used by: `main.py` (lifecycle), `routes/stream.py`, `services/portfolio.py` (price lookups)
- Purpose: Schema management, lazy initialization, connection factory
- Location: `backend/app/db/`
- Contains: `init_db.py` (connection factory + `init_db()`), `schema.py` (SQL DDL + constants)
- Depends on: Python `sqlite3` only
- Used by: `main.py`, `state.py`, all services
- Purpose: Hold process-wide singletons (PriceCache, MarketDataSource, db_path) and provide FastAPI dependency functions
- Location: `backend/app/state.py`
- Contains: `AppState` class, `get_state()`, `get_cache()`, `get_conn()` dependencies
- Used by: All routes
- Purpose: Full trading UI — SPA served as static files by FastAPI
- Location: `backend/static/` (compiled Next.js output, committed to repo)
- Tech: Next.js 15 + TypeScript + Tailwind CSS
- Connects to backend via same-origin `/api/*` endpoints and `EventSource` for SSE
## Data Flow
### Market Data → Browser
### Trade Execution (Manual)
### AI Chat → Auto-Trade
### Portfolio Snapshot (Background)
- Backend: SQLite for durable state; `PriceCache` (in-process dict with threading.Lock) for ephemeral price state
- Frontend: React component state (no Redux/Zustand); SSE events drive price updates
## Key Abstractions
- Purpose: Decouple price production from price consumption — routes/services never know if they're using real or simulated data
- Examples: `backend/app/market/simulator.py` (SimulatorDataSource), `backend/app/market/massive_client.py` (MassiveDataSource)
- Pattern: Abstract Base Class with `start()`, `stop()`, `add_ticker()`, `remove_ticker()`, `get_tickers()`
- Purpose: Thread-safe shared memory between the asyncio market data background task and synchronous FastAPI route handlers
- Location: `backend/app/market/cache.py`
- Pattern: Write-once-per-tick / read-many; version counter for SSE change detection
- Purpose: Immutable price snapshot with computed change/direction properties and `to_dict()` for serialization
- Location: `backend/app/market/models.py`
- Pattern: Frozen dataclass
- Purpose: Single container for process-wide singletons; accessed by routes via FastAPI dependency injection
- Location: `backend/app/state.py`
- Pattern: Request-scoped dependencies (`get_conn`, `get_cache`, `get_state`) wrapping a single process-level object
- Purpose: Typed structured output schema for LLM responses — parsed directly from the LLM JSON
- Location: `backend/app/llm/schema.py`
- Pattern: Pydantic BaseModel used as both the response_format argument to LiteLLM and the auto-execution contract
## Entry Points
- Location: `backend/app/main.py` — `app = create_app()` at module bottom
- Triggers: `uvicorn app.main:app` (CMD in Dockerfile)
- Responsibilities: DB init, market data source startup, background snapshot task, route registration, static file mount
- Location: `backend/app/db/init_db.py` — `init_db(db_path)`
- Triggers: Called by `main.py` lifespan on every startup
- Responsibilities: CREATE TABLE IF NOT EXISTS for all 6 tables, seed default user + watchlist if empty
- Location: `backend/app/market/factory.py` — `create_market_data_source(price_cache)`
- Triggers: Called once in `main.py` lifespan
- Responsibilities: Reads `MASSIVE_API_KEY` env var, returns appropriate `MarketDataSource` implementation
- Location: `backend/app/routes/stream.py` — `GET /api/stream/prices`
- Triggers: Browser `EventSource` connection
- Responsibilities: Yield watchlist-filtered price events every 500ms until client disconnects
## Architectural Constraints
- **Threading:** asyncio event loop for SSE/background tasks; FastAPI sync route handlers run in a thread pool. `PriceCache` uses `threading.Lock` to be safe across both contexts.
- **Global state:** One `AppState` instance attached to `app.state.app_state` (`backend/app/main.py`); `PriceCache` and `MarketDataSource` are process-wide singletons within it.
- **Single user:** All DB queries hard-code `user_id = "default"` (via `DEFAULT_USER_ID` in `backend/app/db/schema.py`). Schema has `user_id` columns for future multi-user support.
- **No ORM:** Raw `sqlite3` connections with `row_factory = sqlite3.Row` throughout the services layer.
- **LLM calls are synchronous within async context:** `litellm.completion()` is called inside `async def handle_chat()` — if not run in a thread it blocks the event loop. Must use `asyncio.to_thread()` or LiteLLM's async API.
- **Circular imports:** None detected in current source. Routes import from services; services import from db and market. One-directional dependency chain.
## Anti-Patterns
### Direct DB calls in LLM handler
### SSE generator opens DB connection per tick
## Error Handling
- `TradeError` in `backend/app/services/portfolio.py` — raised on validation failure (insufficient cash/shares, unknown price)
- `WatchlistError` in `backend/app/services/watchlist.py` — raised on duplicate ticker add
- Market data background tasks catch-all `Exception` with `logger.exception()` and continue looping
- LLM errors propagate as HTTP 500 (no dedicated error type currently)
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| cerebras-inference | Use this to write code to call an LLM using LiteLLM and OpenRouter with the Cerebras inference provider | `.claude/skills/cerebras/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
