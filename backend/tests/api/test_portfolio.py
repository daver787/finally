"""Tests for the portfolio routes.

Routes under test:
  GET  /api/portfolio
  POST /api/portfolio/trade   body {ticker, quantity, side}
  GET  /api/portfolio/history

Prices come from the deterministic test cache (see conftest.TEST_PRICES):
AAPL=190, NVDA=800, etc. Starting cash is the seeded $10,000.
"""

from tests.api.conftest import TEST_PRICES

STARTING_CASH = 10000.0


class TestGetPortfolio:
    """GET /api/portfolio returns cash, positions, total value, and P&L."""

    def test_fresh_portfolio_structure(self, client):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {
            "cash_balance",
            "positions",
            "total_value",
            "total_unrealized_pnl",
        }

    def test_fresh_portfolio_values(self, client):
        body = client.get("/api/portfolio").json()
        assert body["cash_balance"] == STARTING_CASH
        assert body["total_value"] == STARTING_CASH
        assert body["total_unrealized_pnl"] == 0.0
        assert body["positions"] == []

    def test_portfolio_reflects_a_held_position(self, client):
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 2, "side": "buy"},
        )
        body = client.get("/api/portfolio").json()
        assert len(body["positions"]) == 1
        pos = body["positions"][0]
        assert pos["ticker"] == "AAPL"
        assert pos["quantity"] == 2
        assert set(pos) == {
            "ticker",
            "quantity",
            "avg_cost",
            "current_price",
            "unrealized_pnl",
            "pnl_pct",
        }


class TestBuyTrade:
    """POST /api/portfolio/trade with side='buy'."""

    def test_buy_decreases_cash(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
        )
        assert resp.status_code == 200
        body = resp.json()
        expected_cash = STARTING_CASH - 10 * TEST_PRICES["AAPL"]
        assert body["cash_balance"] == round(expected_cash, 2)

    def test_buy_creates_position(self, client):
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "NVDA", "quantity": 1, "side": "buy"},
        )
        body = client.get("/api/portfolio").json()
        nvda = next(p for p in body["positions"] if p["ticker"] == "NVDA")
        assert nvda["quantity"] == 1
        assert nvda["avg_cost"] == TEST_PRICES["NVDA"]

    def test_buy_supports_fractional_quantity(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 2.5, "side": "buy"},
        )
        assert resp.status_code == 200
        pos = next(p for p in resp.json()["positions"] if p["ticker"] == "AAPL")
        assert pos["quantity"] == 2.5

    def test_buy_twice_averages_cost(self, client):
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
        )
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
        )
        body = client.get("/api/portfolio").json()
        aapl = next(p for p in body["positions"] if p["ticker"] == "AAPL")
        # Same price both buys, so avg cost is unchanged and quantity sums.
        assert aapl["quantity"] == 20
        assert aapl["avg_cost"] == TEST_PRICES["AAPL"]

    def test_buy_writes_trade_row(self, client, conn):
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 3, "side": "buy"},
        )
        row = conn.execute(
            "SELECT side, quantity, price FROM trades WHERE ticker = 'AAPL'"
        ).fetchone()
        assert row["side"] == "buy"
        assert row["quantity"] == 3
        assert row["price"] == TEST_PRICES["AAPL"]

    def test_buy_records_snapshot(self, client, conn):
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 1, "side": "buy"},
        )
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM portfolio_snapshots"
        ).fetchone()["n"]
        assert n >= 1

    def test_buy_insufficient_cash_returns_400(self, client):
        # 1000 NVDA @ $800 = $800k, far above the $10k balance.
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "NVDA", "quantity": 1000, "side": "buy"},
        )
        assert resp.status_code == 400
        assert "cash" in resp.json()["detail"].lower()

    def test_buy_unknown_ticker_returns_400(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "ZZZZ", "quantity": 1, "side": "buy"},
        )
        assert resp.status_code == 400


class TestSellTrade:
    """POST /api/portfolio/trade with side='sell'."""

    def _buy(self, client, ticker, qty):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": ticker, "quantity": qty, "side": "buy"},
        )
        assert resp.status_code == 200

    def test_sell_increases_cash(self, client):
        self._buy(client, "AAPL", 10)
        cash_after_buy = client.get("/api/portfolio").json()["cash_balance"]
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 4, "side": "sell"},
        )
        assert resp.status_code == 200
        expected = cash_after_buy + 4 * TEST_PRICES["AAPL"]
        assert resp.json()["cash_balance"] == round(expected, 2)

    def test_partial_sell_decreases_quantity(self, client):
        self._buy(client, "AAPL", 10)
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 3, "side": "sell"},
        )
        body = client.get("/api/portfolio").json()
        aapl = next(p for p in body["positions"] if p["ticker"] == "AAPL")
        assert aapl["quantity"] == 7

    def test_full_sell_removes_from_positions_list(self, client):
        self._buy(client, "AAPL", 5)
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 5, "side": "sell"},
        )
        body = client.get("/api/portfolio").json()
        # Zeroed positions are excluded from the API response.
        assert all(p["ticker"] != "AAPL" for p in body["positions"])

    def test_full_sell_keeps_db_row_at_quantity_zero(self, client, conn):
        self._buy(client, "AAPL", 5)
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 5, "side": "sell"},
        )
        # The positions row must persist with quantity=0, never be deleted.
        row = conn.execute(
            "SELECT quantity FROM positions WHERE ticker = 'AAPL'"
        ).fetchone()
        assert row is not None
        assert row["quantity"] == 0

    def test_oversell_returns_400(self, client):
        self._buy(client, "AAPL", 5)
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "sell"},
        )
        assert resp.status_code == 400
        assert "shares" in resp.json()["detail"].lower()

    def test_sell_never_held_returns_400(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "MSFT", "quantity": 1, "side": "sell"},
        )
        assert resp.status_code == 400

    def test_sell_writes_trade_row(self, client, conn):
        self._buy(client, "AAPL", 5)
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 2, "side": "sell"},
        )
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM trades WHERE ticker = 'AAPL' AND side = 'sell'"
        ).fetchone()
        assert row["n"] == 1


class TestTradeValidation:
    """Request-body validation for POST /api/portfolio/trade."""

    def test_zero_quantity_rejected(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 0, "side": "buy"},
        )
        assert resp.status_code == 422

    def test_negative_quantity_rejected(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": -5, "side": "buy"},
        )
        assert resp.status_code == 422

    def test_invalid_side_rejected(self, client):
        resp = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 1, "side": "hold"},
        )
        assert resp.status_code == 422

    def test_missing_fields_rejected(self, client):
        resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL"})
        assert resp.status_code == 422


class TestPnL:
    """Unrealized P&L math in GET /api/portfolio."""

    def test_pnl_zero_at_purchase_price(self, client):
        # Bought at the same price the cache reports — P&L should be zero.
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
        )
        body = client.get("/api/portfolio").json()
        aapl = next(p for p in body["positions"] if p["ticker"] == "AAPL")
        assert aapl["unrealized_pnl"] == 0.0
        assert aapl["pnl_pct"] == 0.0

    def test_pnl_positive_when_price_rises(self, client, price_cache):
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
        )
        # Push the cached price up after the buy.
        price_cache.update("AAPL", 200.00)
        body = client.get("/api/portfolio").json()
        aapl = next(p for p in body["positions"] if p["ticker"] == "AAPL")
        # 10 shares * ($200 - $190) = $100 gain.
        assert aapl["unrealized_pnl"] == 100.0
        assert aapl["pnl_pct"] > 0

    def test_total_value_includes_position_market_value(self, client):
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
        )
        body = client.get("/api/portfolio").json()
        # Cash spent on the position is offset by its market value at same price.
        assert body["total_value"] == STARTING_CASH


class TestHistory:
    """GET /api/portfolio/history returns portfolio value snapshots."""

    def test_history_empty_before_any_trade(self, client):
        resp = client.get("/api/portfolio/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_history_has_snapshot_after_trade(self, client):
        client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 1, "side": "buy"},
        )
        resp = client.get("/api/portfolio/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) >= 1
        assert set(body[0]) == {"total_value", "recorded_at"}

    def test_history_ordered_oldest_first(self, client):
        for _ in range(3):
            client.post(
                "/api/portfolio/trade",
                json={"ticker": "AAPL", "quantity": 1, "side": "buy"},
            )
        body = client.get("/api/portfolio/history").json()
        timestamps = [row["recorded_at"] for row in body]
        assert timestamps == sorted(timestamps)
