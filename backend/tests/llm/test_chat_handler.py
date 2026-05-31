"""Tests for app.llm.chat — handle_chat (mock + auto-execute + persistence)."""

from __future__ import annotations

from app.llm.chat import MOCK_RESPONSE, handle_chat
from app.llm.schema import ChatResponse, TradeAction, WatchlistChange

from app.db.schema import DEFAULT_USER_ID
from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource


async def test_mock_mode_returns_fixed_response(db_conn, monkeypatch):
    """LLM_MOCK=true returns the fixed PLAN.md §9 response without calling LiteLLM."""
    monkeypatch.setenv("LLM_MOCK", "true")
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    src = SimulatorDataSource(price_cache=cache)

    result = await handle_chat(
        user_message="How is my portfolio?",
        conn=db_conn,
        price_cache=cache,
        market_source=src,
    )

    assert result["message"] == (
        "I've reviewed your portfolio. I'll pick up 1 share of AAPL to demonstrate "
        "trade execution."
    )
    trades = result["executed_actions"]["trades"]
    assert len(trades) == 1
    assert trades[0]["ticker"] == "AAPL"
    assert trades[0]["side"] == "buy"
    assert trades[0]["quantity"] == 1
    assert trades[0]["price"] == 190.0
    assert result["executed_actions"]["errors"] == []


async def test_mock_mode_persists_user_and_assistant_messages(db_conn, monkeypatch):
    """Both the user prompt and the assistant reply are written to chat_messages."""
    monkeypatch.setenv("LLM_MOCK", "true")
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    src = SimulatorDataSource(price_cache=cache)

    await handle_chat(
        user_message="How is my portfolio?",
        conn=db_conn,
        price_cache=cache,
        market_source=src,
    )

    rows = db_conn.execute(
        "SELECT role, content, actions FROM chat_messages "
        "WHERE user_id = ? ORDER BY created_at ASC",
        (DEFAULT_USER_ID,),
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "How is my portfolio?"
    assert rows[0]["actions"] is None
    assert rows[1]["role"] == "assistant"
    assert rows[1]["content"] == (
        "I've reviewed your portfolio. I'll pick up 1 share of AAPL to demonstrate "
        "trade execution."
    )
    assert rows[1]["actions"] is not None
    assert "AAPL" in rows[1]["actions"]


async def test_mock_mode_actually_executes_trade(db_conn, monkeypatch):
    """The mock trade goes through execute_trade — cash and positions update."""
    monkeypatch.setenv("LLM_MOCK", "true")
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    src = SimulatorDataSource(price_cache=cache)

    await handle_chat(
        user_message="Buy something for me",
        conn=db_conn,
        price_cache=cache,
        market_source=src,
    )

    cash_row = db_conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
    ).fetchone()
    assert abs(float(cash_row["cash_balance"]) - 9810.0) < 0.01

    pos_row = db_conn.execute(
        "SELECT quantity FROM positions WHERE user_id = ? AND ticker = ?",
        (DEFAULT_USER_ID, "AAPL"),
    ).fetchone()
    assert pos_row is not None
    assert float(pos_row["quantity"]) == 1.0


async def test_mock_mode_trade_failure_goes_to_errors_list(db_conn, monkeypatch):
    """No price for AAPL → execute_trade raises TradeError → ends up in errors."""
    monkeypatch.setenv("LLM_MOCK", "true")
    cache = PriceCache()  # No AAPL price primed
    src = SimulatorDataSource(price_cache=cache)

    result = await handle_chat(
        user_message="Try a trade",
        conn=db_conn,
        price_cache=cache,
        market_source=src,
    )

    assert result["executed_actions"]["trades"] == []
    errors = result["executed_actions"]["errors"]
    assert len(errors) == 1
    assert errors[0]["ticker"] == "AAPL"
    assert "no price" in errors[0]["error"].lower()


async def test_watchlist_changes_applied_before_trades(db_conn, monkeypatch):
    """watchlist_changes (Pitfall 6) MUST be applied before trades."""
    monkeypatch.setenv("LLM_MOCK", "true")
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache)

    custom_mock = ChatResponse(
        message="Adding PYPL to your watchlist.",
        trades=[],
        watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
    )
    monkeypatch.setattr("app.llm.chat.MOCK_RESPONSE", custom_mock)

    result = await handle_chat(
        user_message="Add PYPL to my watchlist",
        conn=db_conn,
        price_cache=cache,
        market_source=src,
    )

    assert result["message"] == "Adding PYPL to your watchlist."
    rows = db_conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? AND ticker = ?",
        (DEFAULT_USER_ID, "PYPL"),
    ).fetchall()
    assert len(rows) == 1


async def test_history_endpoint_underpinning_chat_messages_table(db_conn, monkeypatch):
    """chat_messages table is the underpinning of GET /api/chat/history."""
    monkeypatch.setenv("LLM_MOCK", "true")
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    src = SimulatorDataSource(price_cache=cache)

    await handle_chat(
        user_message="Test",
        conn=db_conn,
        price_cache=cache,
        market_source=src,
    )

    count_row = db_conn.execute(
        "SELECT COUNT(*) AS n FROM chat_messages WHERE user_id = ?",
        (DEFAULT_USER_ID,),
    ).fetchone()
    assert int(count_row["n"]) == 2

    actions_row = db_conn.execute(
        "SELECT actions FROM chat_messages WHERE role = 'assistant' "
        "ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    assert actions_row is not None
    assert "AAPL" in actions_row["actions"]


async def test_invalid_side_skipped_gracefully(db_conn, monkeypatch):
    """A failed trade still leaves the conversational response intact."""
    monkeypatch.setenv("LLM_MOCK", "true")
    cache = PriceCache()  # No price primed for any ticker
    src = SimulatorDataSource(price_cache=cache)

    custom_mock = ChatResponse(
        message="I will try to buy AAPL.",
        trades=[TradeAction(ticker="AAPL", side="buy", quantity=1)],
        watchlist_changes=[],
    )
    monkeypatch.setattr("app.llm.chat.MOCK_RESPONSE", custom_mock)

    result = await handle_chat(
        user_message="Buy AAPL",
        conn=db_conn,
        price_cache=cache,
        market_source=src,
    )

    assert result["message"] == "I will try to buy AAPL."
    assert result["executed_actions"]["trades"] == []
    assert len(result["executed_actions"]["errors"]) >= 1


# Reference MOCK_RESPONSE so the import is not flagged as unused
_ = MOCK_RESPONSE
