# Market Data Backend — Code Review

**Date:** 2026-05-19
**Reviewer:** Claude Sonnet 4.6
**Scope:** `backend/app/market/` (8 source files, ~350 LOC) and `backend/tests/market/` (6 test files, 73 tests)
**Prior review archived at:** `planning/archive/MARKET_DATA_REVIEW.md` (2026-02-10)

---

## 1. Test Results

**73 tests, 73 passed, 0 failed.**

```
platform darwin -- Python 3.14.5, pytest-9.0.2
asyncio: mode=Mode.AUTO

tests/market/test_cache.py            13 passed
tests/market/test_factory.py           7 passed
tests/market/test_massive.py          13 passed
tests/market/test_models.py           11 passed
tests/market/test_simulator.py        19 passed
tests/market/test_simulator_source.py 10 passed

73 passed in 3.30s
```

All 7 issues from the prior review (Feb 2026) are resolved: the build config, lazy imports, SSE return type annotation, public `get_tickers()` on `GBMSimulator`, correlation constant cleanup, unused test imports, and Massive mock structure.

**Lint (ruff):** Clean — zero warnings or errors across all source and test files.

---

## 2. Coverage

```
Name                           Stmts   Miss  Cover   Missing
------------------------------------------------------------
app/market/__init__.py             6      0   100%
app/market/cache.py               39      0   100%
app/market/factory.py             15      0   100%
app/market/interface.py           13      0   100%
app/market/models.py              26      0   100%
app/market/seed_prices.py          8      0   100%
app/market/simulator.py          139      3    98%   149, 268-269
app/market/massive_client.py      67      4    94%   85-87, 125
app/market/stream.py              36     24    33%   26-48, 62-87
------------------------------------------------------------
TOTAL                            349     31    91%
```

### Coverage gap explanations

| Module | Missed lines | Root cause |
|--------|-------------|-----------|
| `simulator.py:149` | Duplicate guard in `_add_ticker_internal` — the `if ticker in self._prices: return` on line 149 is unreachable because `add_ticker()` already checks this before calling the internal method | Redundant defensive code; safe to keep |
| `simulator.py:268-269` | `logger.exception(...)` inside the `except` block of `_run_loop` — no test injects a failure into `self._sim.step()` | Acceptable gap; exception path is not exercised |
| `massive_client.py:85-87` | Lines inside `_poll_loop` after the first sleep — the single test that starts the loop stops it before the second iteration | Acceptable; first iteration is tested via `test_start_immediate_poll` |
| `massive_client.py:125` | The real body of `_fetch_snapshots` — all tests patch this method at the instance level before it is called | Correct; the real HTTP call cannot run in unit tests |
| `stream.py:26-87` | The entire SSE streaming handler and async generator body | No SSE tests exist (see Issue 3 below) |

---

## 3. Architecture Assessment

The subsystem is cleanly designed and well-executed. The strategy pattern, shared cache, and asyncio lifecycle management are all correct. The GBM math is sound (Itô-correct drift term, Cholesky-correlated moves, log-normal price paths). The architecture will integrate with the rest of the application with minimal friction.

**Strengths:**
- **Strategy pattern with a clean ABC** — `SimulatorDataSource` and `MassiveDataSource` are fully interchangeable; downstream code only imports `MarketDataSource`.
- **`PriceCache` as single source of truth** — producers write, consumers read; no direct coupling.
- **Immutable `PriceUpdate` with `frozen=True, slots=True`** — correct choice for a high-frequency data object.
- **GBM parameter tuning is thoughtful** — TSLA at σ=0.50 vs V at σ=0.17 reflects real-world volatility differences.
- **Correlated moves via Cholesky** — mathematically correct; sector correlation structure is reasonable.
- **Defensive error handling in both data sources** — both background loops catch exceptions and continue; essential for a long-running service.
- **SSE version-based change detection** — avoids sending redundant payloads to connected clients.
- **`asyncio.to_thread` for synchronous HTTP** — correct; keeps the event loop unblocked.
- **Graceful stop** — both sources cancel their tasks cleanly and handle `CancelledError`.

---

## 4. Issues Found

### Issue 1 — Deprecated `asyncio.DefaultEventLoopPolicy` in conftest (Severity: Medium)

**File:** `tests/conftest.py:7-11`

```python
@pytest.fixture
def event_loop_policy():
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
```

Two problems:
1. `asyncio.DefaultEventLoopPolicy` is deprecated in Python 3.12 and slated for removal in Python 3.16. This generates 73 deprecation warnings during the test run (one per test).
2. The fixture is never consumed by any test. `event_loop_policy` is a recognized fixture name by `pytest-asyncio`, but only if the fixture is used by tests or has a wider scope. As written (function scope, returning the policy without being `autouse=True`), it has no effect.

The fixture appears to be leftover scaffolding. It can be removed entirely — `pytest-asyncio` in `auto` mode (as configured in `pyproject.toml`) manages the event loop without needing this fixture.

**Fix:** Delete `tests/conftest.py` content (or the fixture), or replace with:
```python
# conftest.py can be empty or removed
```

---

### Issue 2 — Ticker normalization asymmetry between data sources (Severity: Low)

**File:** `backend/app/market/massive_client.py:67-68` vs `backend/app/market/simulator.py:242-248`

`MassiveDataSource.add_ticker()` normalizes input:
```python
async def add_ticker(self, ticker: str) -> None:
    ticker = ticker.upper().strip()
    ...
```

`SimulatorDataSource.add_ticker()` does not:
```python
async def add_ticker(self, ticker: str) -> None:
    if self._sim:
        self._sim.add_ticker(ticker)  # raw input, no normalization
```

Calling `add_ticker("aapl")` will silently create a new "aapl" entry in the simulator (with a random seed price since it's not in `SEED_PRICES`), while the same call to `MassiveDataSource` correctly adds "AAPL". This divergence would produce incorrect behavior when the app switches between data sources.

**Fix:** Add normalization to `SimulatorDataSource.add_ticker()`:
```python
async def add_ticker(self, ticker: str) -> None:
    ticker = ticker.upper().strip()
    if self._sim:
        self._sim.add_ticker(ticker)
        ...
```

The same normalization should be applied to `remove_ticker()` in `SimulatorDataSource` for consistency.

---

### Issue 3 — `stream.py` has no tests (Severity: Low–Medium)

**File:** `backend/app/market/stream.py` — 33% coverage

The SSE streaming endpoint (`_generate_events`) is completely untested. This is the primary consumer-facing interface — every connected browser client hits this path continuously. The untested logic includes:
- Version-based change detection
- Disconnect detection via `request.is_disconnected()`
- The `retry: 1000\n\n` initial event
- The JSON serialization format sent to clients

Testing SSE generators requires an ASGI test client (Starlette's `TestClient` with `stream=True`, or `httpx.AsyncClient`). Example skeleton:

```python
from starlette.testclient import TestClient
from fastapi import FastAPI
from app.market import PriceCache, create_stream_router

def test_sse_sends_prices():
    cache = PriceCache()
    cache.update("AAPL", 190.50)
    app = FastAPI()
    app.include_router(create_stream_router(cache), prefix="/api")
    # ... assert event format
```

This is the highest-priority gap in the test suite given the SSE stream is the app's real-time data backbone.

---

### Issue 4 — Module-level `router` instance in `create_stream_router` (Severity: Low)

**File:** `backend/app/market/stream.py:17, 20-48`

```python
router = APIRouter(prefix="/api/stream", tags=["streaming"])   # module-level

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    @router.get("/prices")                                      # registers on module router
    async def stream_prices(request: Request) -> StreamingResponse:
        ...
    return router
```

The `router` object is created at module scope. `create_stream_router()` registers a route onto this shared object and returns it. If called a second time (e.g., in two different tests that each create a `FastAPI` app), it registers a second `/prices` route on the same `APIRouter`, causing duplicate route registration. This doesn't affect production (called once at startup) but is a latent footgun for any future testing or multi-app scenarios.

**Fix:** Create the router inside the factory function:
```python
def create_stream_router(price_cache: PriceCache) -> APIRouter:
    router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        ...
    return router
```

---

### Issue 5 — `MassiveDataSource` does not fall back to `day.c` price (Severity: Low)

**File:** `backend/app/market/massive_client.py:100-114`

The Massive API documentation (`planning/MASSIVE_API.md`) explicitly states: *"For FinAlly the most reliable live price is `lastTrade.p` (or fall back to `day.c`)."*

The current implementation skips the ticker entirely if `last_trade` is `None` or raises an `AttributeError`:
```python
try:
    price = snap.last_trade.price           # fails if last_trade is None
    timestamp = snap.last_trade.timestamp / 1000.0
    ...
except (AttributeError, TypeError) as e:
    logger.warning("Skipping snapshot for %s: %s", ...)
```

Outside market hours or during market open when the first trade hasn't occurred yet, `last_trade` may be `None`. The cache will show `None` for these tickers rather than the available closing price.

**Fix:**
```python
price = None
timestamp = None
if snap.last_trade and snap.last_trade.price:
    price = snap.last_trade.price
    timestamp = snap.last_trade.timestamp / 1000.0
elif hasattr(snap, "day") and snap.day and snap.day.close:
    price = snap.day.close

if price is None:
    logger.warning("No price available for %s", snap.ticker)
    continue
```

---

### Issue 6 — `PriceCache.version` read outside the lock (Severity: Trivial)

**File:** `backend/app/market/cache.py:64-66`

```python
@property
def version(self) -> int:
    return self._version   # no lock
```

All other `PriceCache` methods acquire `self._lock`. The `version` property does not. On CPython, reading a single `int` is atomic due to the GIL, so this is safe in practice. However, Python 3.13 introduced an opt-in no-GIL build (PEP 703), and if this code ever runs there, this is a data race. It is also inconsistent with the rest of the class.

The SSE endpoint reads `version` every 500ms in a tight loop, so holding the lock briefly on each read is negligible overhead.

**Fix:**
```python
@property
def version(self) -> int:
    with self._lock:
        return self._version
```

---

## 5. Missing Test Coverage

Beyond Issue 3 (SSE tests), the following scenarios are not covered:

| Gap | Risk | Recommendation |
|-----|------|---------------|
| `GBMSimulator` with all 10 default tickers | Cholesky decomposition could fail for the full correlation matrix (e.g., if the matrix is not positive-definite for an unusual combination) | Add one test: `GBMSimulator(tickers=list(SEED_PRICES.keys()))` and call `step()` |
| `PriceCache` concurrent writes (thread safety) | The lock logic looks correct but is unverified empirically | Optional: a test with multiple threads calling `update()` simultaneously |
| `SimulatorDataSource.add_ticker()` called before `start()` | Currently silently no-ops; could confuse callers | Add a test asserting the ticker is not tracked if added pre-start |
| `MassiveDataSource._poll_loop` second iteration | Lines 85-87 are never hit; the loop's behavior across multiple intervals is untested | Could be covered with `asyncio.sleep` + mock, or accepted as an acceptable gap |

---

## 6. Summary

| Dimension | Status |
|-----------|--------|
| Tests | 73/73 passing |
| Lint | Clean (ruff, zero issues) |
| Coverage | 91% overall; `stream.py` at 33% is the main gap |
| Prior review issues | All 7 resolved |
| New issues found | 6 (1 medium, 3 low, 2 trivial) |
| Architecture | Solid — strategy pattern, clean boundaries, correct async lifecycle |
| GBM math | Correct — Itô drift, Cholesky correlation, log-normal prices |
| Production readiness | Ready for integration; fix Issue 1 (deprecation warning) and Issue 2 (ticker normalization) before connecting the watchlist API |

### Recommended fix priority

1. **Remove deprecated `event_loop_policy` fixture** (Issue 1) — eliminates 73 warnings, prevents breakage on Python 3.16.
2. **Normalize tickers in `SimulatorDataSource`** (Issue 2) — behavioral correctness; will cause subtle bugs when the watchlist API calls `add_ticker("aapl")`.
3. **Move router creation inside `create_stream_router`** (Issue 4) — makes SSE testing possible and removes the latent duplicate-registration bug.
4. **Add SSE integration tests** (Issue 3) — highest-value test addition; covers the live data path.
5. **Add `day.c` fallback in `MassiveDataSource`** (Issue 5) — correctness for out-of-hours data.
6. **Lock `version` property** (Issue 6) — future-proofing for no-GIL Python.
