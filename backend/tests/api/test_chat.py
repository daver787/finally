"""Tests for the POST /api/chat route.

Run with ``LLM_MOCK=true`` so the route uses the fixed mock response and never
calls OpenRouter. The mock buys 1 share of AAPL — with $10k seed cash and AAPL
at $190 in the test cache, the trade always succeeds.
"""

import pytest


@pytest.fixture(autouse=True)
def _force_mock_mode(monkeypatch):
    """Every test in this module exercises the deterministic mock path."""
    monkeypatch.setenv("LLM_MOCK", "true")


class TestChatRoute:
    """POST /api/chat runs a full chat turn end to end."""

    def test_chat_returns_message_and_executed_trade(self, client):
        resp = client.post("/api/chat", json={"message": "Analyze my portfolio"})
        assert resp.status_code == 200
        body = resp.json()
        assert "AAPL" in body["message"]
        assert len(body["trades_executed"]) == 1
        assert body["trades_executed"][0]["ticker"] == "AAPL"
        assert body["trades_executed"][0]["side"] == "buy"
        assert body["trades_executed"][0]["quantity"] == 1
        assert body["watchlist_changes_applied"] == []
        assert body["errors"] == []

    def test_chat_persists_messages(self, client, conn):
        client.post("/api/chat", json={"message": "Buy something"})
        rows = conn.execute(
            "SELECT role, content FROM chat_messages ORDER BY created_at, rowid"
        ).fetchall()
        roles = [r["role"] for r in rows]
        assert roles == ["user", "assistant"]
        assert rows[0]["content"] == "Buy something"

    def test_chat_trade_actually_executes(self, client, conn):
        client.post("/api/chat", json={"message": "Demo a trade"})
        position = conn.execute(
            "SELECT quantity FROM positions WHERE ticker = 'AAPL'"
        ).fetchone()
        assert position is not None
        assert float(position["quantity"]) == 1.0

    def test_chat_missing_message_rejected(self, client):
        resp = client.post("/api/chat", json={})
        assert resp.status_code == 422
