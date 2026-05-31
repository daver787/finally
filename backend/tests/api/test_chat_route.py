"""Integration tests for /api/chat and /api/chat/history."""

from __future__ import annotations


def _prime_price(client, ticker: str, price: float) -> None:
    """Seed the running app's PriceCache so the auto-trade has a deterministic price."""
    client.app.state.app_state.price_cache.update(ticker, price)


def test_chat_endpoint_returns_message_in_mock_mode(client, monkeypatch):
    """POST /api/chat with LLM_MOCK=true returns the structured envelope."""
    monkeypatch.setenv("LLM_MOCK", "true")
    _prime_price(client, "AAPL", 190.0)

    response = client.post("/api/chat", json={"content": "What's in my portfolio?"})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("message"), str)
    actions = body.get("executed_actions")
    assert isinstance(actions, dict)
    assert isinstance(actions.get("trades"), list)
    assert isinstance(actions.get("errors"), list)
    assert isinstance(actions.get("watchlist_changes"), list)


def test_chat_endpoint_mock_executes_aapl_buy(client, monkeypatch):
    """The mock response auto-executes a 1-share AAPL buy that lands in portfolio."""
    monkeypatch.setenv("LLM_MOCK", "true")
    _prime_price(client, "AAPL", 190.0)

    response = client.post("/api/chat", json={"content": "Anything to do?"})
    assert response.status_code == 200
    body = response.json()
    trades = body["executed_actions"]["trades"]
    assert len(trades) == 1
    assert trades[0]["ticker"] == "AAPL"

    portfolio = client.get("/api/portfolio")
    assert portfolio.status_code == 200
    assert abs(portfolio.json()["cash_balance"] - 9810.0) < 0.01


def test_chat_history_returns_empty_list_initially(client):
    """GET /api/chat/history returns [] before any chats."""
    response = client.get("/api/chat/history")
    assert response.status_code == 200
    assert response.json() == []


def test_chat_history_returns_messages_after_chat(client, monkeypatch):
    """After one round-trip the history contains user + assistant rows in ASC order."""
    monkeypatch.setenv("LLM_MOCK", "true")
    _prime_price(client, "AAPL", 190.0)

    post = client.post("/api/chat", json={"content": "hello"})
    assert post.status_code == 200

    history = client.get("/api/chat/history")
    assert history.status_code == 200
    rows = history.json()
    assert isinstance(rows, list)
    assert len(rows) >= 2
    for row in rows:
        assert {"id", "role", "content", "actions", "created_at"}.issubset(row.keys())
    assert rows[0]["role"] == "user"
    assert rows[1]["role"] == "assistant"


def test_chat_endpoint_rejects_missing_content(client):
    """Missing content field → Pydantic 422."""
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


def test_chat_endpoint_rejects_empty_content(client):
    """Empty content string → Pydantic min_length 422."""
    response = client.post("/api/chat", json={"content": ""})
    assert response.status_code == 422
