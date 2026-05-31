"""Tests for /api/watchlist endpoints (GET, POST, DELETE)."""

from __future__ import annotations

REQUIRED_KEYS = {
    "id",
    "ticker",
    "added_at",
    "price",
    "previous_price",
    "change_percent",
    "direction",
}


def test_list_watchlist_returns_seeded_tickers(client):
    response = client.get("/api/watchlist")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 10
    for entry in body:
        assert REQUIRED_KEYS.issubset(entry.keys())


def test_add_ticker_returns_201_and_appears_in_list(client):
    response = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert response.status_code == 201
    body = response.json()
    assert body["ticker"] == "PYPL"  # normalized

    response = client.get("/api/watchlist")
    tickers = {e["ticker"] for e in response.json()}
    assert "PYPL" in tickers
    assert len(response.json()) == 11


def test_add_duplicate_ticker_returns_400(client):
    r1 = client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r1.status_code == 201
    r2 = client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r2.status_code == 400
    assert "PYPL" in r2.json()["detail"]


def test_remove_ticker_returns_204_and_removes(client):
    response = client.delete("/api/watchlist/AAPL")
    assert response.status_code == 204

    response = client.get("/api/watchlist")
    tickers = {e["ticker"] for e in response.json()}
    assert "AAPL" not in tickers


def test_remove_normalizes_ticker_case(client):
    response = client.delete("/api/watchlist/aapl")
    assert response.status_code == 204

    response = client.get("/api/watchlist")
    tickers = {e["ticker"] for e in response.json()}
    assert "AAPL" not in tickers
