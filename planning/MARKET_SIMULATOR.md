# Market Simulator — Approach & Code Structure

The simulator is the default market data source. It runs entirely in-process with no external dependencies, making it suitable for development, testing, and production deployments without a Massive API key.

---

## Overview

The simulator uses **Geometric Brownian Motion (GBM)** — the same stochastic process that underlies the Black-Scholes options pricing model. It produces realistic-looking price series that drift and fluctuate with the statistical properties of real equities. A Cholesky decomposition introduces sector-based **cross-ticker correlations** so tech stocks move together as a group, mirroring real market behavior.

---

## Mathematical Foundation

### Geometric Brownian Motion

Each price step follows:

```
S(t + dt) = S(t) × exp((μ - σ²/2) × dt + σ × √dt × Z)
```

| Symbol | Meaning |
|--------|---------|
| `S(t)` | Current price |
| `μ` (mu) | Annualized drift (expected return) |
| `σ` (sigma) | Annualized volatility |
| `dt` | Time step as a fraction of a trading year |
| `Z` | Standard normal random variable |

**Why GBM?**
- Prices are always positive (exponential transform prevents going negative)
- Log-returns are normally distributed — consistent with empirical finance
- Simple, parameterizable, and fast to compute

### Time Step Calibration

The simulator ticks every 500ms. Expressed as a fraction of a trading year:

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800 seconds
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ≈ 8.48e-8
```

This tiny `dt` produces sub-cent moves per tick that accumulate naturally over minutes and hours, giving the visual impression of live market activity without unrealistic jumps.

### Correlated Moves via Cholesky Decomposition

Instead of drawing independent `Z` values for each ticker, the simulator:

1. Builds an `n × n` correlation matrix `Σ` based on sector membership
2. Computes the Cholesky factor `L` where `Σ = L × Lᵀ`
3. Draws `n` independent standard normals `z`
4. Applies `z_correlated = L @ z`

Each tick, all tickers receive correlated random shocks that respect the sector structure.

**Correlation coefficients:**

| Pair | Coefficient |
|------|------------|
| Both in tech sector | 0.60 |
| Both in finance sector | 0.50 |
| TSLA with anything | 0.30 (behaves independently) |
| Cross-sector | 0.30 |
| Unknown tickers | 0.30 |

---

## Module Structure

### `seed_prices.py` — Configuration Data

Holds all static configuration for the simulator. No logic.

```python
# Realistic starting prices for the 10 default tickers
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
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL": {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT": {"sigma": 0.20, "mu": 0.05},
    "AMZN": {"sigma": 0.28, "mu": 0.05},
    "TSLA": {"sigma": 0.50, "mu": 0.03},   # High volatility
    "NVDA": {"sigma": 0.40, "mu": 0.08},   # High vol + strong upward drift
    "META": {"sigma": 0.30, "mu": 0.05},
    "JPM":  {"sigma": 0.18, "mu": 0.04},   # Low vol (bank)
    "V":    {"sigma": 0.17, "mu": 0.04},   # Low vol (payments)
    "NFLX": {"sigma": 0.35, "mu": 0.05},
}

# Fallback for dynamically-added tickers not in TICKER_PARAMS
DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

# Sector groups for correlation matrix
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech":    {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

# Correlation values
INTRA_TECH_CORR    = 0.6
INTRA_FINANCE_CORR = 0.5
CROSS_GROUP_CORR   = 0.3
TSLA_CORR          = 0.3
```

**Extending:** To add a new ticker with custom behavior, add an entry to `SEED_PRICES` and `TICKER_PARAMS`. If no entry exists, `DEFAULT_PARAMS` applies and the ticker is treated as cross-sector (correlation 0.3 with everything).

---

### `GBMSimulator` (`simulator.py`) — Pure Price Math

`GBMSimulator` is a pure computation object. It knows nothing about asyncio, caches, or the rest of the application. It holds prices in memory and exposes a single `step()` method that advances all tickers by one time step.

```python
class GBMSimulator:
    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ~8.48e-8

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = 0.001,
    ) -> None: ...
```

**Internal state:**

```python
self._tickers: list[str]              # Ordered list (index matches Cholesky matrix)
self._prices: dict[str, float]        # Current price per ticker
self._params: dict[str, dict]         # sigma, mu per ticker
self._cholesky: np.ndarray | None     # L from Cholesky decomposition
self._dt: float                       # Time step
self._event_prob: float               # Probability of a shock event per tick
```

**`step()` — the hot path (called every 500ms):**

```python
def step(self) -> dict[str, float]:
    n = len(self._tickers)
    if n == 0:
        return {}

    # 1. Draw n independent standard normals
    z_independent = np.random.standard_normal(n)

    # 2. Correlate using Cholesky factor
    z_correlated = self._cholesky @ z_independent if self._cholesky else z_independent

    result = {}
    for i, ticker in enumerate(self._tickers):
        mu, sigma = self._params[ticker]["mu"], self._params[ticker]["sigma"]

        # 3. Apply GBM formula
        drift     = (mu - 0.5 * sigma**2) * self._dt
        diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
        self._prices[ticker] *= math.exp(drift + diffusion)

        # 4. Random shock event (~0.1% chance per tick)
        if random.random() < self._event_prob:
            shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])
            self._prices[ticker] *= (1 + shock)

        result[ticker] = round(self._prices[ticker], 2)

    return result
```

**`add_ticker()` / `remove_ticker()`:** Mutate the ticker list, price dict, and params dict, then call `_rebuild_cholesky()` to recompute the correlation matrix with the new set of tickers.

**`_rebuild_cholesky()`:**

```python
def _rebuild_cholesky(self) -> None:
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
```

The Cholesky rebuild is `O(n²)` but `n < 50` in practice, so it is negligible.

---

### `SimulatorDataSource` (`simulator.py`) — AsyncIO Adapter

`SimulatorDataSource` implements `MarketDataSource`. It wraps `GBMSimulator` with an asyncio background task and connects it to the `PriceCache`.

```python
class SimulatorDataSource(MarketDataSource):

    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,       # seconds between ticks
        event_probability: float = 0.001,   # passed to GBMSimulator
    ) -> None: ...
```

**Lifecycle:**

```python
async def start(self, tickers: list[str]) -> None:
    self._sim = GBMSimulator(tickers=tickers, event_probability=self._event_prob)

    # Seed the cache immediately — SSE clients get data on first poll
    for ticker in tickers:
        price = self._sim.get_price(ticker)
        if price is not None:
            self._cache.update(ticker=ticker, price=price)

    # Launch background loop
    self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")

async def stop(self) -> None:
    if self._task and not self._task.done():
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
    self._task = None
```

**Core loop:**

```python
async def _run_loop(self) -> None:
    while True:
        try:
            prices = self._sim.step()               # CPU-bound, but fast (~microseconds)
            for ticker, price in prices.items():
                self._cache.update(ticker=ticker, price=price)
        except Exception:
            logger.exception("Simulator step failed")
        await asyncio.sleep(self._interval)         # yield to event loop
```

**Dynamic ticker management:**

```python
async def add_ticker(self, ticker: str) -> None:
    if self._sim:
        self._sim.add_ticker(ticker)
        price = self._sim.get_price(ticker)         # Seed immediately
        if price is not None:
            self._cache.update(ticker=ticker, price=price)

async def remove_ticker(self, ticker: str) -> None:
    if self._sim:
        self._sim.remove_ticker(ticker)
    self._cache.remove(ticker)
```

---

## Random Shock Events

Every tick, each ticker has a configurable probability (default `0.001` = 0.1%) of experiencing a sudden shock:

```python
if random.random() < self._event_prob:
    shock_magnitude = random.uniform(0.02, 0.05)   # 2–5% move
    shock_sign = random.choice([-1, 1])
    self._prices[ticker] *= (1 + shock_magnitude * shock_sign)
```

With 10 tickers at 2 ticks/second, the expected interval between shocks is:

```
1 / (10 tickers × 2 ticks/sec × 0.001) = 50 seconds
```

This produces a dramatic 2–5% spike roughly once per minute on one of the tickers — visually compelling for a trading terminal demo.

---

## Visual Behavior at 500ms Ticks

At the default `dt ≈ 8.48e-8` (500ms / trading year), a stock with `σ = 0.25` produces a typical move of:

```
σ × √dt = 0.25 × √(8.48e-8) ≈ 0.000073 per tick
```

On a $190 stock that is:

```
$190 × 0.000073 ≈ $0.014 per tick  (1.4 cents)
```

Sub-cent moves accumulate over minutes into visible trends. The price flash animation (CSS background highlight fading over 500ms) fires on every tick, giving a live-data feel even though the individual moves are small.

---

## Dependencies

```toml
# backend/pyproject.toml
[project]
dependencies = [
    "numpy",      # Cholesky decomposition, normal random draws
    "massive",    # Required by MassiveDataSource (not used by simulator itself)
]
```

`numpy` is the only external dependency used by the simulator itself. The GBM math could be implemented with `math` and `random` from the standard library, but `numpy` makes the correlated-draw computation clean and fast.

---

## Testing

The simulator has three dedicated test modules:

| Module | What it tests |
|--------|--------------|
| `tests/market/test_simulator.py` | GBMSimulator: step math, add/remove tickers, Cholesky rebuild, price positivity, shock events |
| `tests/market/test_simulator_source.py` | SimulatorDataSource: start/stop lifecycle, cache seeding, add/remove tickers, loop behavior |
| `tests/market/test_models.py` | PriceUpdate: computed properties (change, direction), to_dict() format |

**Key test assertions for GBMSimulator:**
- All prices remain strictly positive after 1000 steps
- Adding/removing a ticker updates `get_tickers()` correctly
- Cholesky is rebuilt (no `None` reference) after the first ticker is added
- `step()` on an empty ticker list returns `{}`
- Shock events only occur when the random draw is below `event_probability`

---

## Extending the Simulator

### Add a new default ticker

1. Add to `SEED_PRICES` in `seed_prices.py` with a realistic starting price.
2. Add to `TICKER_PARAMS` with calibrated `sigma` and `mu` values.
3. Add to the appropriate sector in `CORRELATION_GROUPS` (or leave out for 0.3 cross-sector correlation).
4. Add to the `DEFAULT_TICKERS` list in the application startup code.

### Adjust volatility

- **Higher `sigma`** (e.g., 0.50 for TSLA) → larger per-tick moves, more dramatic visual swings.
- **Lower `sigma`** (e.g., 0.15 for a utility stock) → smooth, flat-looking price series.
- **Positive `mu`** → upward trend over many minutes; with tiny `dt` the effect is very slow.

### Adjust shock frequency

Pass `event_probability` to `SimulatorDataSource` constructor:

```python
# No shocks (for deterministic tests)
SimulatorDataSource(price_cache, event_probability=0.0)

# Shock every ~10 seconds on average (dramatic demo)
SimulatorDataSource(price_cache, event_probability=0.01)
```

### Change tick rate

Pass `update_interval` to `SimulatorDataSource`:

```python
# 200ms ticks (faster, more CPU usage)
SimulatorDataSource(price_cache, update_interval=0.2)

# 1 second ticks (lower CPU, less visual activity)
SimulatorDataSource(price_cache, update_interval=1.0)
```

Note: `GBMSimulator.DEFAULT_DT` is calibrated for 500ms ticks. If you change `update_interval`, also pass a corresponding `dt` to `GBMSimulator` for mathematically consistent volatility:

```python
interval = 0.2
dt = interval / GBMSimulator.TRADING_SECONDS_PER_YEAR
sim = GBMSimulator(tickers, dt=dt)
```
