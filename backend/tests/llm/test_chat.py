"""Unit tests for the LLM chat handler (``app.llm.chat``).

``handle_chat`` opens its own connection from ``db_path``, so these tests use a
real temp-file SQLite database (not ``:memory:``) seeded with default data.

The LLM call is exercised two ways:
  * ``LLM_MOCK=true`` → the fixed ``MOCK_RESPONSE`` path, no patching needed.
  * mock disabled → ``litellm.completion`` is patched to return a crafted
    ``ChatResponse`` so trade/watchlist/error handling can be driven precisely.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.db import get_db, init_db
from app.llm.chat import handle_chat
from app.llm.schema import ChatResponse, TradeAction, WatchlistChange
from app.market.cache import PriceCache

TEST_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "TSLA": 250.00,
    "NVDA": 800.00,
}


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """An isolated, freshly seeded SQLite database file."""
    path = tmp_path / "finally_test.db"
    init_db(path)
    return str(path)


@pytest.fixture
def price_cache() -> PriceCache:
    """A PriceCache pre-filled with deterministic prices for known tickers."""
    cache = PriceCache()
    for ticker, price in TEST_PRICES.items():
        cache.update(ticker, price)
        cache.update(ticker, price)
    return cache


def _patch_completion(chat_response: ChatResponse):
    """Build a patch for ``litellm.completion`` returning ``chat_response``.

    ``handle_chat`` imports ``completion`` lazily from ``litellm`` inside
    ``_call_llm``, so the patch target is ``litellm.completion`` itself.
    """
    mock_message = MagicMock()
    mock_message.content = chat_response.model_dump_json()
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return patch("litellm.completion", return_value=mock_response)


class TestMockMode:
    """With LLM_MOCK=true the handler uses the fixed mock response."""

    async def test_mock_mode_returns_fixed_message_and_trade(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.setenv("LLM_MOCK", "true")
        result = await handle_chat("Anything", db_path, price_cache)

        assert "AAPL" in result["message"]
        assert len(result["trades_executed"]) == 1
        assert result["trades_executed"][0]["ticker"] == "AAPL"
        assert result["trades_executed"][0]["quantity"] == 1
        assert result["errors"] == []

    async def test_mock_mode_does_not_call_litellm(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.setenv("LLM_MOCK", "true")
        with patch("litellm.completion") as mock_completion:
            await handle_chat("Hello", db_path, price_cache)
        mock_completion.assert_not_called()

    async def test_mock_mode_persists_position(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.setenv("LLM_MOCK", "true")
        await handle_chat("Trade for me", db_path, price_cache)

        conn = get_db(db_path)
        try:
            row = conn.execute(
                "SELECT quantity FROM positions WHERE ticker = 'AAPL'"
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert float(row["quantity"]) == 1.0


class TestTradeExecution:
    """Trades returned by the LLM are auto-executed through the portfolio path."""

    async def test_buy_trade_executes(self, db_path, price_cache, monkeypatch):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(
            message="Buying NVDA.",
            trades=[TradeAction(ticker="NVDA", side="buy", quantity=2)],
        )
        with _patch_completion(response):
            result = await handle_chat("Buy NVDA", db_path, price_cache)

        assert len(result["trades_executed"]) == 1
        trade = result["trades_executed"][0]
        assert trade["ticker"] == "NVDA"
        assert trade["side"] == "buy"
        assert trade["price"] == 800.0
        assert result["errors"] == []

    async def test_sell_trade_executes_after_buy(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        buy = ChatResponse(
            message="Buying.",
            trades=[TradeAction(ticker="AAPL", side="buy", quantity=5)],
        )
        with _patch_completion(buy):
            await handle_chat("Buy AAPL", db_path, price_cache)

        sell = ChatResponse(
            message="Selling.",
            trades=[TradeAction(ticker="AAPL", side="sell", quantity=3)],
        )
        with _patch_completion(sell):
            result = await handle_chat("Sell AAPL", db_path, price_cache)

        assert len(result["trades_executed"]) == 1
        assert result["trades_executed"][0]["side"] == "sell"
        assert result["errors"] == []

        conn = get_db(db_path)
        try:
            row = conn.execute(
                "SELECT quantity FROM positions WHERE ticker = 'AAPL'"
            ).fetchone()
        finally:
            conn.close()
        assert float(row["quantity"]) == 2.0

    async def test_multiple_trades_in_one_turn(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(
            message="Buying two names.",
            trades=[
                TradeAction(ticker="AAPL", side="buy", quantity=1),
                TradeAction(ticker="GOOGL", side="buy", quantity=1),
            ],
        )
        with _patch_completion(response):
            result = await handle_chat("Diversify", db_path, price_cache)

        tickers = {t["ticker"] for t in result["trades_executed"]}
        assert tickers == {"AAPL", "GOOGL"}
        assert result["errors"] == []

    async def test_no_trades_leaves_portfolio_unchanged(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(message="Your portfolio looks balanced.")
        with _patch_completion(response):
            result = await handle_chat("How am I doing?", db_path, price_cache)

        assert result["trades_executed"] == []
        assert result["watchlist_changes_applied"] == []
        assert result["errors"] == []


class TestTradeErrors:
    """Failed trades surface in 'errors' without aborting the turn."""

    async def test_insufficient_cash_reported_as_error(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        # 1000 shares of NVDA @ $800 = $800k, far above the $10k seed cash.
        response = ChatResponse(
            message="Going all in on NVDA.",
            trades=[TradeAction(ticker="NVDA", side="buy", quantity=1000)],
        )
        with _patch_completion(response):
            result = await handle_chat("All in", db_path, price_cache)

        assert result["trades_executed"] == []
        assert len(result["errors"]) == 1
        assert "Insufficient cash" in result["errors"][0]

    async def test_sell_more_than_held_reported_as_error(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(
            message="Selling AAPL.",
            trades=[TradeAction(ticker="AAPL", side="sell", quantity=10)],
        )
        with _patch_completion(response):
            result = await handle_chat("Sell AAPL", db_path, price_cache)

        assert result["trades_executed"] == []
        assert len(result["errors"]) == 1
        assert "Insufficient shares" in result["errors"][0]

    async def test_unknown_ticker_reported_as_error(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(
            message="Buying ZZZZ.",
            trades=[TradeAction(ticker="ZZZZ", side="buy", quantity=1)],
        )
        with _patch_completion(response):
            result = await handle_chat("Buy ZZZZ", db_path, price_cache)

        assert result["trades_executed"] == []
        assert len(result["errors"]) == 1
        assert "ZZZZ" in result["errors"][0]

    async def test_one_failure_does_not_block_other_trades(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(
            message="Two trades.",
            trades=[
                TradeAction(ticker="NVDA", side="buy", quantity=1000),  # fails
                TradeAction(ticker="AAPL", side="buy", quantity=1),  # succeeds
            ],
        )
        with _patch_completion(response):
            result = await handle_chat("Mixed", db_path, price_cache)

        assert len(result["trades_executed"]) == 1
        assert result["trades_executed"][0]["ticker"] == "AAPL"
        assert len(result["errors"]) == 1


class TestWatchlistChanges:
    """Watchlist add/remove actions are applied and errors surface."""

    async def test_add_ticker_to_watchlist(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(
            message="Adding PYPL.",
            watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
        )
        with _patch_completion(response):
            result = await handle_chat("Watch PYPL", db_path, price_cache)

        assert result["watchlist_changes_applied"] == [
            {"ticker": "PYPL", "action": "add"}
        ]
        assert result["errors"] == []

        conn = get_db(db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM watchlist WHERE ticker = 'PYPL'"
            ).fetchone()
        finally:
            conn.close()
        assert row is not None

    async def test_remove_ticker_from_watchlist(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(
            message="Removing AAPL from the watchlist.",
            watchlist_changes=[WatchlistChange(ticker="AAPL", action="remove")],
        )
        with _patch_completion(response):
            result = await handle_chat("Drop AAPL", db_path, price_cache)

        assert result["watchlist_changes_applied"] == [
            {"ticker": "AAPL", "action": "remove"}
        ]
        assert result["errors"] == []

        conn = get_db(db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM watchlist WHERE ticker = 'AAPL'"
            ).fetchone()
        finally:
            conn.close()
        assert row is None

    async def test_duplicate_add_reported_as_error(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        # AAPL is in the default seeded watchlist already.
        response = ChatResponse(
            message="Adding AAPL.",
            watchlist_changes=[WatchlistChange(ticker="AAPL", action="add")],
        )
        with _patch_completion(response):
            result = await handle_chat("Watch AAPL", db_path, price_cache)

        assert result["watchlist_changes_applied"] == []
        assert len(result["errors"]) == 1
        assert "AAPL" in result["errors"][0]

    async def test_remove_missing_ticker_reported_as_error(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(
            message="Removing XYZ.",
            watchlist_changes=[WatchlistChange(ticker="XYZ", action="remove")],
        )
        with _patch_completion(response):
            result = await handle_chat("Drop XYZ", db_path, price_cache)

        assert result["watchlist_changes_applied"] == []
        assert len(result["errors"]) == 1


class TestChatHistory:
    """The user turn and assistant turn are persisted to chat_messages."""

    async def test_both_messages_stored(self, db_path, price_cache, monkeypatch):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(message="Hello back.")
        with _patch_completion(response):
            await handle_chat("Hello there", db_path, price_cache)

        conn = get_db(db_path)
        try:
            rows = conn.execute(
                "SELECT role, content, actions FROM chat_messages "
                "ORDER BY created_at, rowid"
            ).fetchall()
        finally:
            conn.close()

        assert [r["role"] for r in rows] == ["user", "assistant"]
        assert rows[0]["content"] == "Hello there"
        assert rows[0]["actions"] is None
        assert rows[1]["content"] == "Hello back."

    async def test_assistant_actions_stored_as_json(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(
            message="Bought AAPL.",
            trades=[TradeAction(ticker="AAPL", side="buy", quantity=1)],
        )
        with _patch_completion(response):
            await handle_chat("Buy AAPL", db_path, price_cache)

        conn = get_db(db_path)
        try:
            row = conn.execute(
                "SELECT actions FROM chat_messages WHERE role = 'assistant'"
            ).fetchone()
        finally:
            conn.close()

        actions = json.loads(row["actions"])
        assert len(actions["trades_executed"]) == 1
        assert actions["trades_executed"][0]["ticker"] == "AAPL"
        assert actions["errors"] == []

    async def test_prior_history_passed_to_llm(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        first = ChatResponse(message="First reply.")
        with _patch_completion(first):
            await handle_chat("First message", db_path, price_cache)

        second = ChatResponse(message="Second reply.")
        with _patch_completion(second) as mock_completion:
            await handle_chat("Second message", db_path, price_cache)

        sent_messages = mock_completion.call_args.kwargs["messages"]
        contents = [m["content"] for m in sent_messages]
        assert "First message" in contents
        assert "First reply." in contents
        assert "Second message" in contents

    async def test_portfolio_context_included_in_prompt(
        self, db_path, price_cache, monkeypatch
    ):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        response = ChatResponse(message="Noted.")
        with _patch_completion(response) as mock_completion:
            await handle_chat("Status", db_path, price_cache)

        sent_messages = mock_completion.call_args.kwargs["messages"]
        joined = "\n".join(m["content"] for m in sent_messages)
        assert "Cash balance" in joined
        assert "$10,000.00" in joined


class TestMalformedResponse:
    """A malformed LLM payload raises rather than silently passing."""

    async def test_invalid_json_raises(self, db_path, price_cache, monkeypatch):
        monkeypatch.delenv("LLM_MOCK", raising=False)
        mock_message = MagicMock()
        mock_message.content = "not valid json"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.completion", return_value=mock_response):
            with pytest.raises(Exception):
                await handle_chat("Hi", db_path, price_cache)
