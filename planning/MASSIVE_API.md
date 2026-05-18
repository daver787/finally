# Massive API — Stock Market Data Reference

Massive (formerly Polygon.io, rebranded October 30 2025) provides REST APIs, WebSocket streams, and flat-file downloads for US equities, options, forex, crypto, futures, and indices. Existing Polygon.io API keys and integrations continue to work unchanged.

---

## Authentication

Every request must supply an API key. The official Python client handles this automatically; for raw HTTP calls pass the key as a query parameter or Authorization header:

```bash
# Query parameter (simplest)
curl "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT&apiKey=YOUR_API_KEY"

# Authorization header (preferred for production)
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT"
```

**Base URL:** `https://api.massive.com` (legacy `https://api.polygon.io` still resolves)

---

## Rate Limits

| Plan | Requests / min | Data freshness |
|------|---------------|----------------|
| Free (Starter) | 5 | 15-minute delayed |
| Developer | Higher | 15-minute delayed |
| Advanced (Individual) | Higher | Real-time |
| Business | Highest | Real-time + FMV |

When the limit is exceeded the API returns **HTTP 429**. The Python client does not auto-retry — callers must handle this.

**FinAlly default:** poll every 15 seconds on the free tier (≈ 4 req/min for all tickers in one call, well within the 5 req/min cap).

---

## Python Client

```bash
pip install -U massive        # official SDK (formerly polygon-api-client)
```

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_API_KEY")  # reads MASSIVE_API_KEY env var if omitted
```

---

## Key Endpoints

### 1. Full Market Snapshot (primary endpoint for FinAlly)

Fetches the latest price, daily OHLCV, and last trade for a list of tickers in **one API call**.

**HTTP:** `GET /v2/snapshot/locale/us/markets/stocks/tickers`

**Query parameters:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `tickers` | string | No | Comma-separated symbols, case-sensitive. Empty = all tickers. Max ~250. |
| `include_otc` | boolean | No | Include OTC securities. Default: `false`. |
| `apiKey` | string | Yes (if not in header) | Your API key. |

**Example request:**

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient(api_key="YOUR_API_KEY")

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"],
)

for snap in snapshots:
    price = snap.last_trade.price
    ts    = snap.last_trade.timestamp / 1000.0  # ms → seconds
    print(f"{snap.ticker:6s}  ${price:.2f}")
```

**Response structure (abbreviated):**

```json
{
  "count": 10,
  "status": "OK",
  "tickers": [
    {
      "ticker": "AAPL",
      "updated": 1716045600000,
      "todaysChange": 2.45,
      "todaysChangePerc": 1.31,
      "day": {
        "o": 185.00,
        "h": 189.50,
        "l": 184.10,
        "c": 187.45,
        "v": 54321000,
        "vw": 186.78
      },
      "prevDay": {
        "o": 182.00,
        "h": 185.00,
        "l": 181.50,
        "c": 185.00,
        "v": 47000000,
        "vw": 183.50
      },
      "min": {
        "o": 187.00,
        "h": 188.00,
        "l": 186.90,
        "c": 187.45,
        "v": 125000,
        "vw": 187.30,
        "t": 1716045540000
      },
      "lastTrade": {
        "p": 187.45,
        "s": 100,
        "t": 1716045600000,
        "c": [14, 41]
      },
      "lastQuote": {
        "P": 187.46,
        "S": 2,
        "p": 187.45,
        "s": 1,
        "t": 1716045600100
      }
    }
  ]
}
```

**Field reference:**

| Field | Description |
|-------|-------------|
| `ticker` | Exchange symbol |
| `updated` | Last update timestamp (Unix milliseconds) |
| `todaysChange` | Absolute price change from previous close |
| `todaysChangePerc` | Percentage change from previous close |
| `day.c` | Today's closing / current price |
| `day.o/h/l` | Today's open, high, low |
| `day.v` | Today's volume |
| `prevDay.c` | Previous day's close |
| `min.c` | Most recent minute bar close price |
| `lastTrade.p` | Price of the most recent trade |
| `lastTrade.t` | Timestamp of the most recent trade (Unix milliseconds) |
| `lastQuote.P/p` | Best ask / best bid price |
| `fmv` | Fair Market Value — Business plans only |

**For FinAlly** the most reliable live price is `lastTrade.p` (or fall back to `day.c`).

---

### 2. Unified Snapshot (multi-asset, up to 250 tickers)

More flexible than the stocks-specific endpoint; supports filtering and pagination.

**HTTP:** `GET /v3/snapshot`

**Query parameters:**

| Parameter | Type | Notes |
|-----------|------|-------|
| `ticker.any_of` | string | Comma-separated, max 250 |
| `type` | string | `stocks`, `options`, `fx`, `crypto`, `indices` |
| `limit` | integer | Per-page; default 10, max 250 |
| `order` | string | Sort direction |

**Example:**

```python
results = []
for snap in client.list_universal_snapshots(
    params={
        "ticker.any_of": "AAPL,TSLA,NVDA",
        "type": "stocks",
        "limit": 250,
    }
):
    results.append(snap)
```

**Response** includes `last_trade`, `last_quote`, `session` (OHLCV for current session), `market_status`, and `fmv` (Business plans).

---

### 3. Last Trade (single ticker)

Cheapest way to get the current price for one ticker — one call per ticker, so inefficient for multiple tickers. Use the snapshot endpoint instead.

**HTTP:** `GET /v2/last/trade/{ticker}`

```python
trade = client.get_last_trade(ticker="AAPL")
print(f"AAPL last trade: ${trade.price} at {trade.timestamp}")
```

---

### 4. Last Quote (single ticker)

Returns the best bid/ask spread.

**HTTP:** `GET /v2/last/nbbo/{ticker}`

```python
quote = client.get_last_quote(ticker="AAPL")
print(f"AAPL bid: ${quote.bid_price}  ask: ${quote.ask_price}")
```

---

### 5. Aggregate Bars (historical OHLCV)

Historical candlestick data. Useful for seeding charts on first load.

**HTTP:** `GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}`

```python
from datetime import date

bars = []
for bar in client.list_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="minute",
    from_=date(2025, 1, 2),
    to=date(2025, 1, 3),
    limit=50000,
):
    bars.append(bar)

# bar fields: open, high, low, close, volume, vwap, timestamp (ms), transactions
```

**Timespans:** `second`, `minute`, `hour`, `day`, `week`, `month`, `quarter`, `year`

---

### 6. Ticker Reference (company metadata)

Company name, exchange, market cap, SIC code, description, etc.

**HTTP:** `GET /v3/reference/tickers/{ticker}`

```python
details = client.get_ticker_details("AAPL")
print(details.name, details.market_cap, details.primary_exchange)
```

---

## Error Handling

```python
from massive.exceptions import NoResultsError, AuthError, RateLimitError

try:
    snapshots = client.get_snapshot_all(
        market_type=SnapshotMarketType.STOCKS,
        tickers=["AAPL"],
    )
except AuthError:
    # 401 — bad or missing API key
    pass
except RateLimitError:
    # 429 — too many requests; back off and retry
    pass
except NoResultsError:
    # Ticker not found or market is closed
    pass
```

---

## Market Hours & Data Notes

- **Snapshot data is cleared daily at 3:30 AM EST** and repopulates around 4:00 AM EST.
- Outside market hours, `lastTrade` reflects the most recent trade from the prior session.
- Pre-market and after-hours data is available on Advanced and Business plans.
- OTC securities require `include_otc=True`.
- Timestamps are always **Unix milliseconds** in JSON responses. Divide by 1000 to get seconds.

---

## Relevant Links

- [Massive API Docs](https://massive.com/docs)
- [Stocks REST Overview](https://massive.com/docs/rest/stocks/overview)
- [Full Market Snapshot](https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot)
- [Python Client (GitHub)](https://github.com/massive-com/client-python)
- [Rate Limit FAQ](https://massive.com/knowledge-base/categories/rest)
- [Pricing](https://massive.com/pricing)
