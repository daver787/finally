"""Tests for the watchlist routes.

Routes under test:
  GET    /api/watchlist
  POST   /api/watchlist        body {ticker}
  DELETE /api/watchlist/{ticker}
"""

from tests.api.conftest import TEST_PRICES


class TestGetWatchlist:
    """GET /api/watchlist returns the seeded tickers enriched with prices."""

    def test_returns_ten_seed_tickers(self, client):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 10
        assert {e["ticker"] for e in body} == set(TEST_PRICES)

    def test_entries_carry_live_prices(self, client):
        body = client.get("/api/watchlist").json()
        aapl = next(e for e in body if e["ticker"] == "AAPL")
        assert aapl["price"] == TEST_PRICES["AAPL"]
        assert set(aapl) == {"ticker", "price", "prev_price", "change_pct"}

    def test_unknown_ticker_reports_null_price(self, client):
        # A ticker added but never priced by the cache has null price fields.
        client.post("/api/watchlist", json={"ticker": "ZZZZ"})
        body = client.get("/api/watchlist").json()
        zzzz = next(e for e in body if e["ticker"] == "ZZZZ")
        assert zzzz["price"] is None
        assert zzzz["prev_price"] is None
        assert zzzz["change_pct"] is None


class TestAddTicker:
    """POST /api/watchlist adds a ticker and rejects duplicates."""

    def test_add_new_ticker(self, client):
        resp = client.post("/api/watchlist", json={"ticker": "PYPL"})
        assert resp.status_code == 201
        tickers = {e["ticker"] for e in resp.json()}
        assert "PYPL" in tickers
        assert len(resp.json()) == 11

    def test_add_normalizes_to_uppercase(self, client):
        resp = client.post("/api/watchlist", json={"ticker": "pypl"})
        assert resp.status_code == 201
        assert "PYPL" in {e["ticker"] for e in resp.json()}

    def test_add_duplicate_returns_400(self, client):
        resp = client.post("/api/watchlist", json={"ticker": "AAPL"})
        assert resp.status_code == 400

    def test_add_duplicate_case_insensitive(self, client):
        resp = client.post("/api/watchlist", json={"ticker": "aapl"})
        assert resp.status_code == 400

    def test_add_empty_ticker_rejected(self, client):
        resp = client.post("/api/watchlist", json={"ticker": "   "})
        assert resp.status_code == 422

    def test_add_persists_to_db(self, client, conn):
        client.post("/api/watchlist", json={"ticker": "PYPL"})
        row = conn.execute(
            "SELECT ticker FROM watchlist WHERE ticker = 'PYPL'"
        ).fetchone()
        assert row is not None


class TestRemoveTicker:
    """DELETE /api/watchlist/{ticker} removes a ticker; 404 if absent."""

    def test_remove_existing_ticker(self, client):
        resp = client.delete("/api/watchlist/AAPL")
        assert resp.status_code == 200
        assert "AAPL" not in {e["ticker"] for e in resp.json()}
        assert len(resp.json()) == 9

    def test_remove_is_case_insensitive(self, client):
        resp = client.delete("/api/watchlist/aapl")
        assert resp.status_code == 200
        assert "AAPL" not in {e["ticker"] for e in resp.json()}

    def test_remove_missing_ticker_returns_404(self, client):
        resp = client.delete("/api/watchlist/ZZZZ")
        assert resp.status_code == 404

    def test_remove_persists_to_db(self, client, conn):
        client.delete("/api/watchlist/AAPL")
        row = conn.execute(
            "SELECT ticker FROM watchlist WHERE ticker = 'AAPL'"
        ).fetchone()
        assert row is None
