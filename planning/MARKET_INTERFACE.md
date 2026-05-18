# Market Data Interface — Unified Python API

This document specifies the unified market data interface used in FinAlly. The interface decouples all downstream code (SSE streaming, portfolio valuation, trade execution) from the data source. Two concrete implementations exist: a GBM simulator (default) and a Massive REST API client (when `MASSIVE_API_KEY` is set).

---

## Module Layout

```
backend/app/market/
├── __init__.py          # Public re-exports
├── models.py            # PriceUpdate dataclass
├── interface.py         # MarketDataSource ABC
├── cache.py             # PriceCache (thread-safe in-memory store)
├── seed_prices.py       # Seed prices + GBM params for default tickers
├── simulator.py         # GBMSimulator + SimulatorDataSource
├── massive_client.py    # MassiveDataSource (REST polling)
├── factory.py           # create_market_data_source() — selects impl
└── stream.py            # FastAPI SSE router factory
```

---

## Data Model

### `PriceUpdate` (`models.py`)

Immutable frozen dataclass representing a single price tick.

```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: float          # Unix seconds

    # Computed properties
    @property
    def change(self) -> float: ...         # price - previous_price
    @property
    def change_percent(self) -> float: ... # % change from previous
    @property
    def direction(self) -> str: ...        # "up" | "down" | "flat"
    def to_dict(self) -> dict: ...         # JSON-serializable
```

`to_dict()` output (what gets sent over SSE):

```json
{
  "ticker": "AAPL",
  "price": 191.23,
  "previous_price": 190.98,
  "timestamp": 1716045600.123,
  "change": 0.25,
  "change_percent": 0.131,
  "direction": "up"
}
```

---

## Abstract Interface

### `MarketDataSource` (`interface.py`)

All market data sources implement this contract. Downstream code interacts only with this type — never with a concrete implementation.

```python
class MarketDataSource(ABC):

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates for the given tickers.

        Starts a background asyncio task. Must be called exactly once.
        After start(), prices appear in the PriceCache on the source's
        own schedule (500ms for simulator, configurable for Massive).
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task and release resources.

        Cancels the asyncio task and clears the client reference.
        Safe to call multiple times. After stop() the cache is not updated.
        """

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present.

        The next update cycle will include this ticker. For the simulator,
        also seeds the cache immediately with an initial price.
        """

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active set and from the PriceCache.

        No-op if not present.
        """

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the list of actively tracked tickers."""
```

---

## Price Cache

### `PriceCache` (`cache.py`)

Single in-memory store shared between the data source (writer) and all consumers (readers). Thread-safe via `threading.Lock`.

```python
class PriceCache:

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Write a new price. Auto-computes change from previous. Bumps version."""

    def get(self, ticker: str) -> PriceUpdate | None:
        """Latest PriceUpdate for a ticker, or None."""

    def get_price(self, ticker: str) -> float | None:
        """Convenience: just the float price, or None."""

    def get_all(self) -> dict[str, PriceUpdate]:
        """Shallow-copy snapshot of all current prices."""

    def remove(self, ticker: str) -> None:
        """Remove a ticker (called on watchlist removal)."""

    @property
    def version(self) -> int:
        """Monotonically increasing counter. Incremented on every update.
        Used by the SSE endpoint for change detection (no polling overhead)."""
```

**Thread-safety:** The simulator writes from an asyncio background task; the Massive client uses `asyncio.to_thread()` for the synchronous HTTP call. All writes and reads are protected by the same `Lock`.

---

## Factory

### `create_market_data_source()` (`factory.py`)

Single entry point for the application. Returns an **unstarted** source.

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        return SimulatorDataSource(price_cache=price_cache)
```

**Environment variable:** `MASSIVE_API_KEY`
- Set and non-empty → `MassiveDataSource` (real market data)
- Absent or empty → `SimulatorDataSource` (GBM simulation, no external dependencies)

---

## Application Lifecycle

### FastAPI startup/shutdown (typical integration)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.market import PriceCache, create_market_data_source

price_cache = PriceCache()
market_source = None

DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
                   "NVDA", "META", "JPM", "V", "NFLX"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global market_source
    market_source = create_market_data_source(price_cache)
    await market_source.start(DEFAULT_TICKERS)
    yield
    await market_source.stop()

app = FastAPI(lifespan=lifespan)
```

### Reading prices (anywhere in the app)

```python
# Single ticker
update: PriceUpdate | None = price_cache.get("AAPL")
price: float | None = price_cache.get_price("AAPL")

# All tickers (e.g., for portfolio valuation)
all_prices: dict[str, PriceUpdate] = price_cache.get_all()
current_price = all_prices.get("TSLA")

# JSON for API responses
if update:
    return update.to_dict()
```

### Dynamic watchlist management (API route handlers)

```python
# Add a ticker (watchlist POST handler)
await market_source.add_ticker("PYPL")

# Remove a ticker (watchlist DELETE handler)
await market_source.remove_ticker("NFLX")

# Read back current tickers
tickers: list[str] = market_source.get_tickers()
```

---

## SSE Streaming

### `create_stream_router()` (`stream.py`)

Returns a FastAPI `APIRouter` with the SSE endpoint. Attach it to the app during setup.

```python
from app.market import create_stream_router

router = create_stream_router(price_cache)
app.include_router(router, prefix="/api")
# Registers: GET /api/stream/prices
```

**How the SSE endpoint works:**

1. Client connects via `EventSource("/api/stream/prices")`
2. Server reads `price_cache.version` at the start of each loop iteration
3. If version has changed since last send, fetch `price_cache.get_all()` and push all current prices as a JSON event
4. Sleep 100ms, repeat
5. On client disconnect, the generator exits and the connection closes

This version-based approach means the SSE endpoint never calls the market data source directly — it only reads from the cache, maintaining the producer/consumer separation.

**SSE event format:**

```
event: prices
data: {"AAPL": {"ticker": "AAPL", "price": 191.23, ...}, "TSLA": {...}, ...}

```

---

## Public Imports (`__init__.py`)

```python
from app.market import (
    PriceUpdate,          # models.py
    PriceCache,           # cache.py
    MarketDataSource,     # interface.py
    create_market_data_source,  # factory.py
    create_stream_router,       # stream.py
)
```

---

## Design Decisions

### Strategy Pattern
Both `SimulatorDataSource` and `MassiveDataSource` implement `MarketDataSource`. The rest of the application only imports `MarketDataSource` — it never references a concrete type. Swapping data sources requires only a change to the factory's environment variable check.

### PriceCache as the Single Source of Truth
Producers (`SimulatorDataSource`, `MassiveDataSource`) write to the cache. Every consumer (SSE, portfolio valuation, trade execution) reads from the cache. There is no direct coupling between producers and consumers.

### Asyncio-safe Synchronous HTTP
The `massive` Python client is synchronous. `MassiveDataSource` wraps each HTTP call in `asyncio.to_thread()` so the event loop is never blocked.

### Graceful Degradation
If the Massive API returns an error (network failure, 429, 401), `_poll_once()` logs the error and continues — the cache retains the last known prices. The SSE stream keeps flowing with slightly stale data rather than crashing.

### No Direct Polling by Consumers
Consumers never poll the data source. They read from the cache. This keeps the data flow strictly one-directional and avoids thundering-herd problems when multiple SSE connections are open.
