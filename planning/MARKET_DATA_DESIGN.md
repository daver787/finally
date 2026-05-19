# Market Data Backend — Detailed Design

Implementation-ready design for the FinAlly market data subsystem. Covers the unified interface, in-memory price cache, GBM simulator, Massive API client, SSE streaming endpoint, and FastAPI lifecycle integration.

All code lives under `backend/app/market/`.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [File Structure](#2-file-structure)
3. [Data Model — `models.py`](#3-data-model)
4. [Price Cache — `cache.py`](#4-price-cache)
5. [Abstract Interface — `interface.py`](#5-abstract-interface)
6. [Seed Prices & Ticker Parameters — `seed_prices.py`](#6-seed-prices--ticker-parameters)
7. [GBM Simulator — `simulator.py`](#7-gbm-simulator)
8. [Massive API Client — `massive_client.py`](#8-massive-api-client)
9. [Factory — `factory.py`](#9-factory)
10. [SSE Streaming Endpoint — `stream.py`](#10-sse-streaming-endpoint)
11. [Public Package API — `__init__.py`](#11-public-package-api)
12. [FastAPI Lifecycle Integration](#12-fastapi-lifecycle-integration)
13. [Watchlist Coordination](#13-watchlist-coordination)
14. [Testing Strategy](#14-testing-strategy)
15. [Error Handling & Edge Cases](#15-error-handling--edge-cases)
16. [Configuration Reference](#16-configuration-reference)

---

## 1. Architecture Overview

```
MarketDataSource (ABC)
├── SimulatorDataSource  →  GBM simulator (default, no API key needed)
└── MassiveDataSource    →  Polygon.io REST poller (when MASSIVE_API_KEY set)
        │
        ▼
   PriceCache (thread-safe, in-memory)
        │
        ├──→ SSE stream endpoint (/api/stream/prices)
        ├──→ Portfolio valuation   (GET /api/portfolio)
        └──→ Trade execution       (POST /api/portfolio/trade)
```

### Key design principles

**Strategy pattern** — both `SimulatorDataSource` and `MassiveDataSource` implement the same `MarketDataSource` ABC. The rest of the application imports only `MarketDataSource`; swapping data sources is a one-env-var change.

**PriceCache as the single source of truth** — producers (simulator/Massive) write to the cache. Every consumer (SSE, portfolio valuation, trade execution) reads from the cache. There is no direct coupling between producers and consumers.

**Push, not pull** — data sources push into the cache on their own schedule. Consumers read from the cache on their own schedule. The two schedules are completely independent.

**Asyncio-safe synchronous HTTP** — the `massive` Python client is synchronous. `MassiveDataSource` wraps each HTTP call in `asyncio.to_thread()` so the event loop is never blocked.

---

## 2. File Structure

```
backend/
  app/
    market/
      __init__.py         # Public re-exports: 5 names
      models.py           # PriceUpdate dataclass
      cache.py            # PriceCache (thread-safe in-memory store)
      interface.py        # MarketDataSource ABC
      seed_prices.py      # SEED_PRICES, TICKER_PARAMS, CORRELATION_GROUPS, etc.
      simulator.py        # GBMSimulator + SimulatorDataSource
      massive_client.py   # MassiveDataSource (REST polling)
      factory.py          # create_market_data_source() — selects impl
      stream.py           # FastAPI SSE router factory
  tests/
    market/
      __init__.py
      test_models.py
      test_cache.py
      test_simulator.py
      test_simulator_source.py
      test_factory.py
      test_massive.py
```

Each file has a single responsibility. The `__init__.py` re-exports the public API so that the rest of the backend imports from `app.market` without reaching into submodules.

---

## 3. Data Model

**File: `backend/app/market/models.py`**

`PriceUpdate` is the only data structure that leaves the market data layer. Every downstream consumer works exclusively with this type.

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute price change from previous update."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Percentage change from previous update."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
```

`to_dict()` output (what the SSE endpoint sends to the frontend):

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

### Design notes

- **`frozen=True`** — price updates are immutable value objects. Safe to share across async tasks without copying.
- **`slots=True`** — minor memory optimization; we create many of these per second.
- **Computed properties** (`change`, `change_percent`, `direction`) — derived from `price` and `previous_price` so they can never be stale or inconsistent.
- **`to_dict()`** — single serialization point used by both SSE and REST API responses.

---

## 4. Price Cache

**File: `backend/app/market/cache.py`**

The price cache is the central data hub. Data sources write to it; SSE streaming and portfolio valuation read from it. Thread-safe via `threading.Lock` (not `asyncio.Lock`) because the Massive client runs in `asyncio.to_thread()`, a real OS thread.

```python
from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
    Readers: SSE streaming endpoint, portfolio valuation, trade execution.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every update

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price for a ticker. Returns the created PriceUpdate.

        Automatically computes direction and change from the previous price.
        If this is the first update for the ticker, previous_price == price (direction='flat').
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        """Get the latest price for a single ticker, or None if unknown."""
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Snapshot of all current prices. Returns a shallow copy."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        """Convenience: get just the price float, or None."""
        update = self.get(ticker)
        return update.price if update else None

    def remove(self, ticker: str) -> None:
        """Remove a ticker from the cache (e.g., when removed from watchlist)."""
        with self._lock:
            self._prices.pop(ticker, None)

    @property
    def version(self) -> int:
        """Current version counter. Useful for SSE change detection."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

### Why a version counter?

The SSE streaming loop polls the cache every ~500ms. Without a version counter, it would serialize and send all prices every tick even if nothing changed (e.g., Massive API only updates every 15s). The version counter lets the SSE loop skip sends when nothing is new:

```python
last_version = -1
while True:
    current_version = price_cache.version
    if current_version != last_version:
        last_version = current_version
        yield format_sse(price_cache.get_all())
    await asyncio.sleep(0.5)
```

### Thread safety rationale

`threading.Lock` is used instead of `asyncio.Lock` because:
- The Massive client's synchronous `get_snapshot_all()` runs in `asyncio.to_thread()`, which operates in a real OS thread — `asyncio.Lock` would not protect against that.
- The GBM simulator's `step()` is CPU-bound and runs on the event loop but could be offloaded to a thread executor without code changes.
- `threading.Lock` works correctly from both sync threads and the async event loop.

---

## 5. Abstract Interface

**File: `backend/app/market/interface.py`**

All market data sources implement this contract. Downstream code interacts only with this type — never with a concrete implementation.

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache on their own
    schedule. Downstream code never calls the data source directly for prices —
    it reads from the cache.

    Lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL", ...])
        # ... app runs ...
        await source.add_ticker("TSLA")
        await source.remove_ticker("GOOGL")
        # ... app shutting down ...
        await source.stop()
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates for the given tickers.

        Starts a background task that periodically writes to the PriceCache.
        Must be called exactly once. Calling start() twice is undefined behavior.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task and release resources.

        Safe to call multiple times. After stop(), the source will not write
        to the cache again.
        """

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present.

        The next update cycle will include this ticker.
        """

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active set. No-op if not present.

        Also removes the ticker from the PriceCache.
        """

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the current list of actively tracked tickers."""
```

### Why the source writes to the cache instead of returning prices

This push model decouples timing. The simulator ticks at 500ms; Massive polls at 15s; SSE reads from the cache at its own 500ms cadence. The SSE layer never needs to know which data source is active or what its update interval is.

---

## 6. Seed Prices & Ticker Parameters

**File: `backend/app/market/seed_prices.py`**

Constants only — no logic, no imports. Shared by the simulator (initial prices and GBM parameters) and as a fallback price reference for any component that needs a sane default before the first poll.

```python
"""Seed prices and per-ticker parameters for the market simulator."""

# Realistic starting prices for the default watchlist
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "AMZN": 185.00,
    "TSLA": 250.00,
    "NVDA": 800.00,
    "META": 500.00,
    "JPM": 195.00,
    "V":    280.00,
    "NFLX": 600.00,
}

# Per-ticker GBM parameters (annualized)
# sigma: annualized volatility (higher = more price movement per tick)
# mu:    annualized drift / expected return
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT":  {"sigma": 0.20, "mu": 0.05},
    "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA":  {"sigma": 0.50, "mu": 0.03},  # High volatility
    "NVDA":  {"sigma": 0.40, "mu": 0.08},  # High vol + strong upward drift
    "META":  {"sigma": 0.30, "mu": 0.05},
    "JPM":   {"sigma": 0.18, "mu": 0.04},  # Low vol (bank)
    "V":     {"sigma": 0.17, "mu": 0.04},  # Low vol (payments)
    "NFLX":  {"sigma": 0.35, "mu": 0.05},
}

# Fallback for dynamically-added tickers not in TICKER_PARAMS
DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

# Sector groups for correlation matrix construction
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech":    {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

# Correlation coefficients used in the Cholesky decomposition
INTRA_TECH_CORR    = 0.6   # Tech stocks move together
INTRA_FINANCE_CORR = 0.5   # Finance stocks move together
CROSS_GROUP_CORR   = 0.3   # Between sectors / unknown tickers
TSLA_CORR          = 0.3   # TSLA does its own thing
```

**Extending:** to add a new default ticker, add entries to `SEED_PRICES` and `TICKER_PARAMS`, optionally add to a `CORRELATION_GROUPS` sector, then add to `DEFAULT_TICKERS` in the app startup code. If no entry exists, `DEFAULT_PARAMS` applies and correlation defaults to 0.3 with everything.

---

## 7. GBM Simulator

**File: `backend/app/market/simulator.py`**

Two classes in this file:
- **`GBMSimulator`** — pure price math engine. Stateful, synchronous. No asyncio, no caches, no I/O.
- **`SimulatorDataSource`** — the `MarketDataSource` implementation. Wraps `GBMSimulator` in an asyncio background task and writes to `PriceCache`.

### 7.1 Mathematical Foundation

Each price step follows Geometric Brownian Motion (GBM):

```
S(t + dt) = S(t) × exp((μ - σ²/2) × dt + σ × √dt × Z)
```

| Symbol | Meaning |
|--------|---------|
| `S(t)` | Current price |
| `μ` (mu) | Annualized drift (expected return) |
| `σ` (sigma) | Annualized volatility |
| `dt` | Time step as a fraction of a trading year |
| `Z` | Standard normal random variable (correlated across tickers) |

**Why GBM?**
- Prices are always positive (exponential transform prevents negatives)
- Log-returns are normally distributed — consistent with empirical finance
- Simple, parameterizable, fast to compute

**Time step calibration:**

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800 seconds
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ≈ 8.48e-8
```

This tiny `dt` produces sub-cent moves per tick (≈$0.014 on a $190 stock with σ=0.22) that accumulate naturally over minutes into visible trends.

**Correlated moves via Cholesky decomposition:**

Instead of drawing independent `Z` values per ticker, the simulator:
1. Builds an `n × n` correlation matrix `Σ` based on sector membership
2. Computes the Cholesky factor `L` where `Σ = L × Lᵀ`
3. Draws `n` independent standard normals `z`
4. Applies `z_correlated = L @ z`

All tickers receive correlated random shocks on every tick that respect sector structure — tech stocks move together, finance stocks move together, cross-sector correlation is lower.

### 7.2 GBMSimulator — Full Implementation

```python
from __future__ import annotations

import asyncio
import logging
import math
import random

import numpy as np

from .cache import PriceCache
from .interface import MarketDataSource
from .seed_prices import (
    CORRELATION_GROUPS,
    CROSS_GROUP_CORR,
    DEFAULT_PARAMS,
    INTRA_FINANCE_CORR,
    INTRA_TECH_CORR,
    SEED_PRICES,
    TICKER_PARAMS,
    TSLA_CORR,
)

logger = logging.getLogger(__name__)


class GBMSimulator:
    """Geometric Brownian Motion simulator for correlated stock prices."""

    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ~8.48e-8

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = 0.001,
    ) -> None:
        self._dt = dt
        self._event_prob = event_probability

        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None

        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def step(self) -> dict[str, float]:
        """Advance all tickers by one time step. Returns {ticker: new_price}.

        Called every 500ms. Keep it fast.
        """
        n = len(self._tickers)
        if n == 0:
            return {}

        # Draw n independent standard normals, then correlate
        z_independent = np.random.standard_normal(n)
        z_correlated = self._cholesky @ z_independent if self._cholesky is not None else z_independent

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            mu    = self._params[ticker]["mu"]
            sigma = self._params[ticker]["sigma"]

            drift     = (mu - 0.5 * sigma ** 2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            # Random shock: ~0.1% chance per tick (~1 event per 50s across 10 tickers)
            if random.random() < self._event_prob:
                shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])
                self._prices[ticker] *= 1 + shock
                logger.debug("Random event on %s: %.1f%%", ticker, shock * 100)

            result[ticker] = round(self._prices[ticker], 2)

        return result

    def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the simulation. Rebuilds the correlation matrix."""
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the simulation. Rebuilds the correlation matrix."""
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        """Current price for a ticker, or None if not tracked."""
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        """Return the list of currently tracked tickers."""
        return list(self._tickers)

    def _add_ticker_internal(self, ticker: str) -> None:
        """Add without rebuilding Cholesky (for batch init)."""
        if ticker in self._prices:
            return
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        """Rebuild Cholesky decomposition. O(n²) but n < 50 in practice."""
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return

        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = corr[j, i] = rho

        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        """Correlation coefficient between two tickers based on sector.

        tech-tech: 0.6 | finance-finance: 0.5 | TSLA: 0.3 | cross: 0.3
        """
        tech    = CORRELATION_GROUPS["tech"]
        finance = CORRELATION_GROUPS["finance"]

        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

### 7.3 SimulatorDataSource — Async Wrapper

```python
class SimulatorDataSource(MarketDataSource):
    """MarketDataSource backed by the GBM simulator.

    Runs a background asyncio task that calls GBMSimulator.step() every
    `update_interval` seconds and writes results to the PriceCache.
    """

    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,
        event_probability: float = 0.001,
    ) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(
            tickers=tickers,
            event_probability=self._event_prob,
        )
        # Seed the cache immediately — SSE clients get data on their first poll
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)

        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
        logger.info("Simulator started with %d tickers", len(tickers))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Simulator stopped")

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
            logger.info("Simulator: added ticker %s", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)
        logger.info("Simulator: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        """Core loop: step the simulation, write to cache, sleep."""
        while True:
            try:
                if self._sim:
                    prices = self._sim.step()
                    for ticker, price in prices.items():
                        self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

### 7.4 Shock Events

Every tick, each ticker has a configurable probability (default `0.001` = 0.1%) of a sudden shock:

```python
if random.random() < self._event_prob:
    shock_magnitude = random.uniform(0.02, 0.05)   # 2–5% move
    shock_sign      = random.choice([-1, 1])
    self._prices[ticker] *= 1 + shock_magnitude * shock_sign
```

With 10 tickers at 2 ticks/second, expected interval between shocks:

```
1 / (10 × 2 × 0.001) = 50 seconds
```

This produces a dramatic 2–5% spike roughly once per minute on one ticker — visually compelling without being absurd.

### 7.5 Adjusting simulator behavior

```python
# No shocks (deterministic tests)
SimulatorDataSource(price_cache, event_probability=0.0)

# Faster ticks (more CPU, more visual activity)
SimulatorDataSource(price_cache, update_interval=0.2)

# Match dt to a non-default interval for correct volatility math
interval = 0.2
dt = interval / GBMSimulator.TRADING_SECONDS_PER_YEAR
sim = GBMSimulator(tickers, dt=dt)
```

---

## 8. Massive API Client

**File: `backend/app/market/massive_client.py`**

Polls the Massive (formerly Polygon.io) REST API snapshot endpoint on a configurable interval. The synchronous Massive SDK runs in `asyncio.to_thread()`.

```python
from __future__ import annotations

import asyncio
import logging

from massive import RESTClient
from massive.rest.models import SnapshotMarketType

from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)


class MassiveDataSource(MarketDataSource):
    """MarketDataSource backed by the Massive (Polygon.io) REST API.

    Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
    tickers in a single API call, then writes results to the PriceCache.

    Rate limits:
      - Free tier: 5 req/min → poll every 15s (default)
      - Paid tiers: higher limits → poll every 2–5s
    """

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)

        # Immediate first poll so the cache has data right away
        await self._poll_once()

        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info(
            "Massive poller started: %d tickers, %.1fs interval",
            len(tickers),
            self._interval,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None
        logger.info("Massive poller stopped")

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)
            logger.info("Massive: added ticker %s (will appear on next poll)", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)
        logger.info("Massive: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    async def _poll_loop(self) -> None:
        """Poll on interval. First poll already happened in start()."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Execute one poll cycle: fetch snapshots, update cache."""
        if not self._tickers or not self._client:
            return

        try:
            # Massive RESTClient is synchronous — run in a thread
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            processed = 0
            for snap in snapshots:
                try:
                    price = snap.last_trade.price
                    # Massive timestamps are Unix milliseconds → convert to seconds
                    timestamp = snap.last_trade.timestamp / 1000.0
                    self._cache.update(
                        ticker=snap.ticker,
                        price=price,
                        timestamp=timestamp,
                    )
                    processed += 1
                except (AttributeError, TypeError) as e:
                    logger.warning(
                        "Skipping snapshot for %s: %s",
                        getattr(snap, "ticker", "???"),
                        e,
                    )
            logger.debug("Massive poll: updated %d/%d tickers", processed, len(self._tickers))

        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            # Don't re-raise — the loop retries on the next interval.
            # Common failures: 401 (bad key), 429 (rate limit), network errors.

    def _fetch_snapshots(self) -> list:
        """Synchronous call to the Massive REST API. Runs in asyncio.to_thread()."""
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

### Error handling philosophy

| Error | Behavior |
|-------|----------|
| 401 Unauthorized | Logged as error. Poller keeps running (fix `.env`, restart). |
| 429 Rate Limited | Logged as error. Retries after `poll_interval` seconds. |
| Network timeout | Logged as error. Retries automatically on next cycle. |
| Malformed snapshot | Individual ticker skipped with warning. Others still processed. |
| All tickers fail | Cache retains last-known prices. SSE keeps streaming stale data. |

**Stale data vs. no data:** retaining the last-known price in the cache is always better than crashing or going blank. The frontend's connection status indicator stays green (SSE connection is fine), and prices simply stop moving until the API recovers.

### Snapshot field selection

The most reliable live price is `snap.last_trade.price`. Fallback hierarchy if needed:

```python
# Primary: last trade price
price = snap.last_trade.price

# Fallback 1: current minute bar close
if price is None:
    price = snap.min.c

# Fallback 2: today's session close/current price
if price is None:
    price = snap.day.c
```

For after-hours or pre-market, `last_trade.price` reflects the most recent trade from any session on paid plans.

---

## 9. Factory

**File: `backend/app/market/factory.py`**

Single entry point for the application. Returns an **unstarted** source.

```python
from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Create the appropriate market data source based on environment variables.

    - MASSIVE_API_KEY set and non-empty → MassiveDataSource (real market data)
    - Otherwise → SimulatorDataSource (GBM simulation)

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(price_cache=price_cache)
```

**Usage at app startup:**

```python
price_cache = PriceCache()
source = create_market_data_source(price_cache)
await source.start(["AAPL", "GOOGL", "MSFT", ...])
```

---

## 10. SSE Streaming Endpoint

**File: `backend/app/market/stream.py`**

A FastAPI router that holds open long-lived HTTP connections and pushes all cached prices to the client as `text/event-stream`. Uses a factory pattern to receive the `PriceCache` by injection rather than via globals.

```python
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["streaming"])


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Create the SSE streaming router with a reference to the price cache."""

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        """SSE endpoint — GET /api/stream/prices

        Client connects with EventSource; server pushes all ticker prices
        whenever the cache version changes, at most every 500ms.

        Wire format:
            retry: 1000

            data: {"AAPL": {ticker, price, previous_price, ...}, ...}

        """
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted price events."""
    # Browser will reconnect after 1 second if the connection drops
    yield "retry: 1000\n\n"

    last_version = -1
    client_ip = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client_ip)

    try:
        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected: %s", client_ip)
                break

            current_version = price_cache.version
            if current_version != last_version:
                last_version = current_version
                prices = price_cache.get_all()
                if prices:
                    data = {ticker: update.to_dict() for ticker, update in prices.items()}
                    yield f"data: {json.dumps(data)}\n\n"

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for: %s", client_ip)
```

### SSE wire format

Each event the client receives:

```
retry: 1000

data: {"AAPL":{"ticker":"AAPL","price":190.50,"previous_price":190.42,"timestamp":1707580800.5,"change":0.08,"change_percent":0.042,"direction":"up"},"GOOGL":{...}}

```

### Frontend consumption

```javascript
const es = new EventSource('/api/stream/prices');

es.onmessage = (event) => {
    const prices = JSON.parse(event.data);
    // prices: { "AAPL": { ticker, price, previous_price, change, change_percent, direction, timestamp }, ... }
    for (const [ticker, update] of Object.entries(prices)) {
        updateWatchlistRow(ticker, update);     // flash green/red
        appendSparklinePoint(ticker, update.price);
    }
};

es.onerror = () => {
    setConnectionStatus('reconnecting');  // EventSource auto-reconnects
};
```

### Why poll-and-push instead of event-driven push

The SSE endpoint polls the cache version on a fixed 500ms interval rather than being notified by the data source when it writes. This is simpler and produces regular, evenly-spaced updates for the frontend. The frontend accumulates these into sparkline charts — regular spacing is important for clean visualization.

---

## 11. Public Package API

**File: `backend/app/market/__init__.py`**

```python
"""Market data subsystem for FinAlly.

Public API:
    PriceUpdate               - Immutable price snapshot dataclass
    PriceCache                - Thread-safe in-memory price store
    MarketDataSource          - Abstract interface for data providers
    create_market_data_source - Factory: selects simulator or Massive
    create_stream_router      - FastAPI router factory for SSE endpoint
"""

from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import PriceUpdate
from .stream import create_stream_router

__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
]
```

**Consumer code imports from `app.market` only — never from submodules:**

```python
from app.market import PriceCache, create_market_data_source
from app.market import PriceUpdate           # for type annotations
from app.market import create_stream_router  # for SSE setup
```

---

## 12. FastAPI Lifecycle Integration

**File: `backend/app/main.py`**

The market data system starts and stops with the FastAPI application using the `lifespan` context manager.

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException

from app.market import PriceCache, MarketDataSource, create_market_data_source, create_stream_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---

    # 1. Shared price cache (single instance for the process lifetime)
    price_cache = PriceCache()
    app.state.price_cache = price_cache

    # 2. Market data source (selected by MASSIVE_API_KEY env var)
    source = create_market_data_source(price_cache)
    app.state.market_source = source

    # 3. Load initial tickers from the database watchlist
    initial_tickers = await db.get_watchlist_tickers()  # reads from SQLite
    await source.start(initial_tickers)

    # 4. Register the SSE router
    stream_router = create_stream_router(price_cache)
    app.include_router(stream_router)

    yield  # App is running

    # --- SHUTDOWN ---
    await source.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)


# FastAPI dependencies for injection into route handlers
def get_price_cache() -> PriceCache:
    return app.state.price_cache

def get_market_source() -> MarketDataSource:
    return app.state.market_source
```

### Reading prices from route handlers

```python
from fastapi import APIRouter, Depends
from app.market import PriceCache, PriceUpdate

router = APIRouter(prefix="/api")


@router.get("/watchlist")
async def get_watchlist(
    price_cache: PriceCache = Depends(get_price_cache),
):
    tickers = await db.get_watchlist_tickers()
    result = []
    for ticker in tickers:
        update: PriceUpdate | None = price_cache.get(ticker)
        result.append({
            "ticker": ticker,
            "price": update.price if update else None,
            "change_percent": update.change_percent if update else None,
            "direction": update.direction if update else "flat",
        })
    return result


@router.post("/portfolio/trade")
async def execute_trade(
    trade: TradeRequest,
    price_cache: PriceCache = Depends(get_price_cache),
):
    current_price = price_cache.get_price(trade.ticker)
    if current_price is None:
        raise HTTPException(
            status_code=400,
            detail=f"Price not yet available for {trade.ticker}. Please wait a moment.",
        )
    # ... execute trade at current_price ...
```

### Getting all prices for portfolio valuation

```python
@router.get("/portfolio")
async def get_portfolio(
    price_cache: PriceCache = Depends(get_price_cache),
):
    positions = await db.get_positions()
    all_prices = price_cache.get_all()  # dict[str, PriceUpdate]

    enriched = []
    for position in positions:
        update = all_prices.get(position.ticker)
        current_price = update.price if update else position.avg_cost
        unrealized_pnl = (current_price - position.avg_cost) * position.quantity
        enriched.append({
            "ticker": position.ticker,
            "quantity": position.quantity,
            "avg_cost": position.avg_cost,
            "current_price": current_price,
            "unrealized_pnl": round(unrealized_pnl, 2),
        })
    return enriched
```

---

## 13. Watchlist Coordination

When the watchlist changes (via REST API or LLM chat), the market data source must be notified so it tracks the right set of tickers.

### Flow: Adding a ticker

```
User → POST /api/watchlist {ticker: "PYPL"}
  → Validate ticker symbol (basic sanity check)
  → Insert into watchlist table (SQLite)
  → await source.add_ticker("PYPL")
      Simulator: adds to GBMSimulator, rebuilds Cholesky, seeds cache immediately
      Massive:   appends to ticker list, appears on next poll (≤15s)
  → Return {ticker, price} (price may be None for Massive until first poll)
```

### Flow: Removing a ticker

```
User → DELETE /api/watchlist/PYPL
  → Check if user holds a position in PYPL
  → Delete from watchlist table (SQLite)
  → if no open position:
        await source.remove_ticker("PYPL")   # removes from sim + cache
  → Return success
```

### Route implementations

```python
@router.post("/watchlist")
async def add_to_watchlist(
    payload: WatchlistAdd,
    source: MarketDataSource = Depends(get_market_source),
    price_cache: PriceCache = Depends(get_price_cache),
):
    ticker = payload.ticker.upper().strip()
    if not ticker.isalpha() or len(ticker) > 5:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    await db.insert_watchlist(ticker)
    await source.add_ticker(ticker)

    update = price_cache.get(ticker)
    return {"ticker": ticker, "price": update.price if update else None}


@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    source: MarketDataSource = Depends(get_market_source),
):
    ticker = ticker.upper()
    await db.delete_watchlist(ticker)

    # Keep tracking if user holds a position (needed for portfolio P&L)
    position = await db.get_position(ticker)
    if position is None or position.quantity == 0:
        await source.remove_ticker(ticker)

    return {"status": "ok"}
```

### LLM-triggered watchlist changes

The chat endpoint calls the same route logic (or the same underlying db + source operations) after parsing the LLM's structured output:

```python
for change in llm_response.watchlist_changes:
    if change.action == "add":
        await source.add_ticker(change.ticker)
        await db.insert_watchlist(change.ticker)
    elif change.action == "remove":
        await source.remove_ticker(change.ticker)
        await db.delete_watchlist(change.ticker)
```

---

## 14. Testing Strategy

### 14.1 Unit Tests: `PriceUpdate` (`test_models.py`)

```python
from app.market.models import PriceUpdate

class TestPriceUpdate:

    def test_direction_up(self):
        u = PriceUpdate(ticker="AAPL", price=191.0, previous_price=190.0)
        assert u.direction == "up"
        assert u.change == 1.0
        assert u.change_percent == pytest.approx(0.5263, rel=1e-3)

    def test_direction_down(self):
        u = PriceUpdate(ticker="AAPL", price=189.0, previous_price=190.0)
        assert u.direction == "down"
        assert u.change == -1.0

    def test_flat(self):
        u = PriceUpdate(ticker="AAPL", price=190.0, previous_price=190.0)
        assert u.direction == "flat"
        assert u.change == 0.0

    def test_to_dict_keys(self):
        u = PriceUpdate(ticker="AAPL", price=191.0, previous_price=190.0, timestamp=1.0)
        d = u.to_dict()
        assert set(d.keys()) == {
            "ticker", "price", "previous_price", "timestamp",
            "change", "change_percent", "direction"
        }

    def test_zero_previous_price(self):
        u = PriceUpdate(ticker="AAPL", price=100.0, previous_price=0.0)
        assert u.change_percent == 0.0  # No division by zero
```

### 14.2 Unit Tests: `PriceCache` (`test_cache.py`)

```python
from app.market.cache import PriceCache

class TestPriceCache:

    def test_first_update_is_flat(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.direction == "flat"
        assert update.previous_price == 190.50

    def test_direction_tracks_movement(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        up = cache.update("AAPL", 191.00)
        assert up.direction == "up"
        down = cache.update("AAPL", 189.00)
        assert down.direction == "down"

    def test_version_increments_per_update(self):
        cache = PriceCache()
        v0 = cache.version
        cache.update("AAPL", 190.00)
        cache.update("GOOGL", 175.00)
        assert cache.version == v0 + 2

    def test_get_all_returns_copy(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        snapshot = cache.get_all()
        cache.update("AAPL", 191.00)
        # Snapshot should not reflect the second update
        assert snapshot["AAPL"].price == 190.00

    def test_remove_clears_ticker(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.remove("AAPL")
        assert cache.get("AAPL") is None
        assert "AAPL" not in cache

    def test_get_price_convenience(self):
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("NOPE") is None

    def test_thread_safety(self):
        """Concurrent updates should not corrupt the cache."""
        import threading
        cache = PriceCache()
        errors = []

        def writer(start_price):
            try:
                for i in range(100):
                    cache.update("AAPL", start_price + i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(100 * i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert cache.get("AAPL") is not None
```

### 14.3 Unit Tests: `GBMSimulator` (`test_simulator.py`)

```python
from app.market.simulator import GBMSimulator
from app.market.seed_prices import SEED_PRICES

class TestGBMSimulator:

    def test_step_returns_all_tickers(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        result = sim.step()
        assert set(result.keys()) == {"AAPL", "GOOGL"}

    def test_prices_always_positive(self):
        """GBM exp() transform ensures prices never go negative."""
        sim = GBMSimulator(tickers=["AAPL", "TSLA"], event_probability=0.0)
        for _ in range(10_000):
            prices = sim.step()
            assert all(p > 0 for p in prices.values())

    def test_initial_price_matches_seed(self):
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim.get_price("AAPL") == SEED_PRICES["AAPL"]

    def test_unknown_ticker_gets_random_seed(self):
        sim = GBMSimulator(tickers=["ZZZZ"])
        price = sim.get_price("ZZZZ")
        assert 50.0 <= price <= 300.0

    def test_empty_step_returns_empty_dict(self):
        sim = GBMSimulator(tickers=[])
        assert sim.step() == {}

    def test_add_ticker(self):
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("TSLA")
        assert "TSLA" in sim.get_tickers()
        result = sim.step()
        assert "TSLA" in result

    def test_remove_ticker(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        sim.remove_ticker("GOOGL")
        assert "GOOGL" not in sim.get_tickers()
        result = sim.step()
        assert "GOOGL" not in result

    def test_add_duplicate_is_noop(self):
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("AAPL")
        assert sim.get_tickers().count("AAPL") == 1

    def test_cholesky_none_with_single_ticker(self):
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim._cholesky is None

    def test_cholesky_rebuilt_on_second_ticker(self):
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("GOOGL")
        assert sim._cholesky is not None

    def test_prices_drift_over_many_steps(self):
        sim = GBMSimulator(tickers=["AAPL"], event_probability=0.0)
        for _ in range(1000):
            sim.step()
        assert sim.get_price("AAPL") != SEED_PRICES["AAPL"]

    def test_shock_events_occur_with_nonzero_probability(self):
        """With event_probability=1.0, every tick is a shock event."""
        sim = GBMSimulator(tickers=["AAPL"], event_probability=1.0)
        initial = sim.get_price("AAPL")
        prices = sim.step()
        # A 2-5% move means the price can't possibly stay within 1% of initial
        assert abs(prices["AAPL"] - initial) / initial > 0.01
```

### 14.4 Integration Tests: `SimulatorDataSource` (`test_simulator_source.py`)

```python
import asyncio
import pytest
from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource


@pytest.mark.asyncio
class TestSimulatorDataSource:

    async def test_start_populates_cache_immediately(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache)
        await source.start(["AAPL", "GOOGL"])
        # Cache must have data before any loop tick runs
        assert cache.get("AAPL") is not None
        assert cache.get("GOOGL") is not None
        await source.stop()

    async def test_prices_update_over_time(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
        await source.start(["AAPL"])
        v1 = cache.version
        await asyncio.sleep(0.3)
        v2 = cache.version
        assert v2 > v1  # Version must have advanced (prices updated)
        await source.stop()

    async def test_stop_is_idempotent(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache)
        await source.start(["AAPL"])
        await source.stop()
        await source.stop()  # Should not raise

    async def test_add_ticker_appears_in_cache(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache)
        await source.start(["AAPL"])
        await source.add_ticker("TSLA")
        assert "TSLA" in source.get_tickers()
        assert cache.get("TSLA") is not None
        await source.stop()

    async def test_remove_ticker_clears_cache(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache)
        await source.start(["AAPL", "TSLA"])
        await source.remove_ticker("TSLA")
        assert "TSLA" not in source.get_tickers()
        assert cache.get("TSLA") is None
        await source.stop()
```

### 14.5 Unit Tests: `MassiveDataSource` (mocked) (`test_massive.py`)

```python
from unittest.mock import MagicMock, patch
import pytest
from app.market.cache import PriceCache
from app.market.massive_client import MassiveDataSource


def make_snapshot(ticker: str, price: float, ts_ms: int = 1707580800000) -> MagicMock:
    snap = MagicMock()
    snap.ticker = ticker
    snap.last_trade.price = price
    snap.last_trade.timestamp = ts_ms
    return snap


@pytest.mark.asyncio
class TestMassiveDataSource:

    async def test_poll_updates_cache(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._client = MagicMock()
        source._tickers = ["AAPL", "GOOGL"]

        snapshots = [make_snapshot("AAPL", 190.50), make_snapshot("GOOGL", 175.25)]
        with patch.object(source, "_fetch_snapshots", return_value=snapshots):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("GOOGL") == 175.25

    async def test_timestamp_converted_from_ms_to_seconds(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._client = MagicMock()
        source._tickers = ["AAPL"]

        ts_ms = 1707580800000
        with patch.object(source, "_fetch_snapshots", return_value=[make_snapshot("AAPL", 190.0, ts_ms)]):
            await source._poll_once()

        assert cache.get("AAPL").timestamp == ts_ms / 1000.0

    async def test_malformed_snapshot_skipped(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._client = MagicMock()
        source._tickers = ["AAPL", "BAD"]

        good = make_snapshot("AAPL", 190.50)
        bad = MagicMock()
        bad.ticker = "BAD"
        bad.last_trade = None  # AttributeError when accessed

        with patch.object(source, "_fetch_snapshots", return_value=[good, bad]):
            await source._poll_once()  # Must not raise

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("BAD") is None

    async def test_api_error_does_not_crash(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._client = MagicMock()
        source._tickers = ["AAPL"]

        with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
            await source._poll_once()  # Must not raise

        assert cache.get_price("AAPL") is None

    async def test_add_and_remove_ticker(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]

        await source.add_ticker("tsla")  # lowercase — should normalize
        assert "TSLA" in source.get_tickers()

        await source.remove_ticker("TSLA")
        assert "TSLA" not in source.get_tickers()

    async def test_remove_ticker_clears_cache(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=60.0)
        source._tickers = ["AAPL"]
        cache.update("AAPL", 190.00)

        await source.remove_ticker("AAPL")
        assert cache.get("AAPL") is None
```

### 14.6 Unit Tests: `factory.py` (`test_factory.py`)

```python
import pytest
from unittest.mock import patch
from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.simulator import SimulatorDataSource
from app.market.massive_client import MassiveDataSource


def test_no_api_key_returns_simulator():
    cache = PriceCache()
    with patch.dict("os.environ", {}, clear=True):
        source = create_market_data_source(cache)
    assert isinstance(source, SimulatorDataSource)


def test_empty_api_key_returns_simulator():
    cache = PriceCache()
    with patch.dict("os.environ", {"MASSIVE_API_KEY": ""}):
        source = create_market_data_source(cache)
    assert isinstance(source, SimulatorDataSource)


def test_whitespace_api_key_returns_simulator():
    cache = PriceCache()
    with patch.dict("os.environ", {"MASSIVE_API_KEY": "   "}):
        source = create_market_data_source(cache)
    assert isinstance(source, SimulatorDataSource)


def test_api_key_set_returns_massive():
    cache = PriceCache()
    with patch.dict("os.environ", {"MASSIVE_API_KEY": "my-real-key"}):
        source = create_market_data_source(cache)
    assert isinstance(source, MassiveDataSource)
```

---

## 15. Error Handling & Edge Cases

### 15.1 Empty watchlist at startup

If the database has no watchlist entries, `start()` receives an empty list. Both data sources handle this gracefully — the simulator produces no prices, the Massive poller skips its API call. The SSE endpoint sends empty events. When the user adds a ticker, the source starts tracking it immediately.

### 15.2 Price cache miss during trade

```python
price = price_cache.get_price(ticker)
if price is None:
    raise HTTPException(
        status_code=400,
        detail=f"Price not yet available for {ticker}. Please wait a moment and try again.",
    )
```

The simulator avoids this by seeding the cache in `add_ticker()`. The Massive client may have a brief gap on newly-added tickers (up to `poll_interval` seconds). The 400 with a clear message is correct behavior.

### 15.3 Invalid Massive API key

If the key is set but invalid, the first poll fails with a 401. The poller logs the error and keeps retrying. The SSE endpoint streams empty data. The connection status indicator stays green (SSE is fine, no data is available). The fix is to correct the key and restart.

### 15.4 Ticker has an open position

When the user removes a ticker from the watchlist but still holds shares, continue tracking the ticker so portfolio valuation remains accurate. The watchlist DELETE route checks for this (see Section 13).

### 15.5 GBM numerical precision

GBM with tiny `dt` produces very small per-tick moves. Floating-point precision is not a concern because:
- Prices are `round()`ed to 2 decimal places after each step
- The exponential formulation is numerically stable
- Prices are always strictly positive (exp is always > 0)

### 15.6 Cholesky decomposition failure

`np.linalg.cholesky()` can fail if the correlation matrix is not positive definite. This can happen with a badly-constructed matrix (e.g., all correlations = 1.0). The current coefficient choices (0.3–0.6) produce well-conditioned matrices. If a future change causes instability, wrap `_rebuild_cholesky()` in a try/except that falls back to `self._cholesky = None` (independent draws):

```python
try:
    self._cholesky = np.linalg.cholesky(corr)
except np.linalg.LinAlgError:
    logger.warning("Cholesky decomposition failed; using independent draws")
    self._cholesky = None
```

### 15.7 Concurrency: multiple SSE clients

Multiple simultaneous SSE clients all read from the same `PriceCache`. The cache's `threading.Lock` handles this. There is no per-client state in the cache — each client's SSE generator holds its own `last_version` counter locally. Under heavy load (e.g., 100 concurrent SSE connections), the only shared resource is the lock, and the critical sections are tiny (dict copy, version read).

---

## 16. Configuration Reference

All tunable parameters and their defaults:

| Parameter | Location | Default | Notes |
|-----------|----------|---------|-------|
| `MASSIVE_API_KEY` | Environment variable | `""` (empty) | If set → Massive; otherwise → simulator |
| `update_interval` | `SimulatorDataSource.__init__` | `0.5s` | Time between simulator ticks |
| `poll_interval` | `MassiveDataSource.__init__` | `15.0s` | Time between Massive API polls (free tier limit) |
| `event_probability` | `GBMSimulator.__init__` | `0.001` | Per-ticker per-tick shock probability |
| `dt` | `GBMSimulator.__init__` | `~8.5e-8` | GBM time step (fraction of a trading year) |
| SSE push interval | `_generate_events()` | `0.5s` | Cache check cadence per connected client |
| SSE retry | `_generate_events()` | `1000ms` | Browser reconnection delay |

### Correlation structure

| Pair | Coefficient |
|------|------------|
| Both in tech sector (AAPL, GOOGL, MSFT, AMZN, META, NVDA, NFLX) | 0.60 |
| Both in finance sector (JPM, V) | 0.50 |
| TSLA with anything | 0.30 (behaves independently) |
| Cross-sector | 0.30 |
| Unknown tickers | 0.30 |

### Typical tick sizes (σ=0.22, $190 stock, dt=8.48e-8)

```
σ × √dt = 0.22 × √(8.48e-8) ≈ 6.4e-5 per tick (fractional)
$190 × 6.4e-5 ≈ $0.012 per tick (1.2 cents)
```

These sub-cent moves accumulate over minutes into visible trends and produce the live-data feel. The price flash CSS animation fires on every tick regardless of move size.
