"""Tests for the /api/portfolio endpoints (GET, POST /trade, GET /history)."""

from __future__ import annotations


def _prime_price(client, ticker: str, price: float) -> None:
    """Seed the running app's PriceCache so trades have a deterministic price.

    The ``client`` fixture spins up a full app via TestClient with the
    simulator; the simulator is non-deterministic on a 500ms cadence, so for
    integration tests we directly mutate the cache after lifespan startup.
    """
    client.app.state.app_state.price_cache.update(ticker, price)


def test_portfolio_returns_seeded_user(client):
    response = client.get("/api/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == 10000.0
    assert body["total_value"] == 10000.0
    assert body["positions"] == []


def test_portfolio_returns_live_valuation_after_trade(client):
    _prime_price(client, "AAPL", 190.0)
    buy = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 2}
    )
    assert buy.status_code == 200

    response = client.get("/api/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert abs(body["cash_balance"] - 9620.0) < 0.01
    assert isinstance(body["positions"], list)
    assert len(body["positions"]) == 1
    pos = body["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 2.0
    assert pos["current_price"] == 190.0


def test_trade_endpoint_buy_returns_200(client):
    _prime_price(client, "AAPL", 190.0)
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "aapl", "side": "buy", "quantity": 1}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"  # normalized
    assert body["price"] == 190.0
    assert abs(body["cash_balance"] - 9810.0) < 0.01


def test_trade_endpoint_buy_insufficient_cash_returns_400(client):
    _prime_price(client, "AAPL", 190.0)
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 1000},
    )
    assert response.status_code == 400
    assert "insufficient" in response.json()["detail"].lower()


def test_trade_endpoint_sell_without_position_returns_400(client):
    _prime_price(client, "AAPL", 190.0)
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 1}
    )
    assert response.status_code == 400
    assert "insufficient" in response.json()["detail"].lower()


def test_trade_endpoint_invalid_side_returns_422(client):
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "hold", "quantity": 1}
    )
    assert response.status_code == 422


def test_trade_endpoint_negative_quantity_returns_422(client):
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": -1}
    )
    assert response.status_code == 422


def test_trade_endpoint_unknown_ticker_returns_400(client):
    # ZZZZ is not seeded in the cache; trade should fail with "no price"
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "ZZZZ", "side": "buy", "quantity": 1}
    )
    assert response.status_code == 400
    assert "no price" in response.json()["detail"].lower()


def test_history_endpoint_returns_list(client):
    _prime_price(client, "AAPL", 190.0)
    client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1}
    )
    response = client.get("/api/portfolio/history")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    for entry in body:
        assert "total_value" in entry and isinstance(entry["total_value"], (int, float))
        assert "recorded_at" in entry and isinstance(entry["recorded_at"], str)


def test_history_endpoint_empty_returns_list(client):
    """History returns a list. Task 4 adds a startup snapshot, so length may be >= 1.

    Kept forward-compatible: we only assert the shape (list), not the count.
    """
    response = client.get("/api/portfolio/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
