"""LLM chat handler for FinAlly.

``handle_chat`` runs one full conversation turn: it builds portfolio context,
calls the LLM (or a fixed mock), auto-executes any trades / watchlist changes
the LLM requests, and persists both sides of the exchange to ``chat_messages``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from app.db import get_db
from app.db.schema import DEFAULT_USER_ID
from app.market.cache import PriceCache
from app.services import portfolio as pf
from app.services import watchlist as wl

from .schema import ChatResponse, TradeAction, WatchlistChange

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

CHAT_HISTORY_LIMIT = 100

SYSTEM_PROMPT = (
    "You are FinAlly, an AI trading assistant embedded in a simulated trading "
    "workstation. You help the user analyze and manage a virtual portfolio "
    "funded with fake money — there is no real-world risk.\n\n"
    "Your responsibilities:\n"
    "- Analyze portfolio composition, risk concentration, and P&L.\n"
    "- Suggest trades with clear, data-driven reasoning.\n"
    "- Execute trades when the user asks for them or agrees to a suggestion.\n"
    "- Manage the watchlist proactively when relevant.\n"
    "- Be concise and data-driven; avoid filler.\n\n"
    "You must always respond with valid structured JSON matching the required "
    "schema. The 'message' field is the conversational text shown to the user. "
    "Put any trades to execute in 'trades' and any watchlist edits in "
    "'watchlist_changes'. Only include trades/watchlist changes the user wants "
    "or has agreed to — leave the arrays empty otherwise. Trades execute "
    "automatically with no confirmation dialog."
)

MOCK_RESPONSE = ChatResponse(
    message=(
        "I've reviewed your portfolio. I'll pick up 1 share of AAPL to "
        "demonstrate trade execution."
    ),
    trades=[TradeAction(ticker="AAPL", side="buy", quantity=1)],
    watchlist_changes=[],
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _llm_mock_enabled() -> bool:
    return os.getenv("LLM_MOCK", "").strip().lower() == "true"


def _build_portfolio_context(
    conn: sqlite3.Connection, cache: PriceCache, user_id: str
) -> str:
    """Render the user's current portfolio + watchlist as a context string."""
    portfolio = pf.get_portfolio(conn, cache, user_id)
    watchlist = wl.get_watchlist(conn, cache, user_id)

    lines = [
        "Current portfolio state:",
        f"- Cash balance: ${portfolio['cash_balance']:,.2f}",
        f"- Total portfolio value: ${portfolio['total_value']:,.2f}",
        f"- Total unrealized P&L: ${portfolio['total_unrealized_pnl']:,.2f}",
    ]

    if portfolio["positions"]:
        lines.append("- Positions:")
        for p in portfolio["positions"]:
            lines.append(
                f"  - {p['ticker']}: {p['quantity']} shares @ avg "
                f"${p['avg_cost']:,.2f}, now ${p['current_price']:,.2f}, "
                f"unrealized P&L ${p['unrealized_pnl']:,.2f} "
                f"({p['pnl_pct']:+.2f}%)"
            )
    else:
        lines.append("- Positions: none")

    if watchlist:
        lines.append("- Watchlist:")
        for w in watchlist:
            price = (
                f"${w['price']:,.2f}" if w["price"] is not None else "no price yet"
            )
            lines.append(f"  - {w['ticker']}: {price}")
    else:
        lines.append("- Watchlist: empty")

    return "\n".join(lines)


def _load_history(
    conn: sqlite3.Connection, user_id: str
) -> list[dict[str, str]]:
    """Load the last ``CHAT_HISTORY_LIMIT`` messages, oldest-first."""
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE user_id = ? "
        "ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (user_id, CHAT_HISTORY_LIMIT),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _call_llm(messages: list[dict[str, str]]) -> ChatResponse:
    """Call the LLM via LiteLLM/OpenRouter and parse the structured response."""
    from litellm import completion

    response = completion(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )
    result = response.choices[0].message.content
    return ChatResponse.model_validate_json(result)


def _apply_trades(
    conn: sqlite3.Connection,
    cache: PriceCache,
    trades: list[TradeAction],
    user_id: str,
) -> tuple[list[dict], list[str]]:
    """Execute each requested trade; collect successes and error strings."""
    executed: list[dict] = []
    errors: list[str] = []
    for trade in trades:
        try:
            result = pf.execute_trade(
                conn, cache, trade.ticker, trade.quantity, trade.side, user_id
            )
            executed.append(result)
        except pf.TradeError as exc:
            errors.append(
                f"Trade failed ({trade.side} {trade.quantity} {trade.ticker}): {exc}"
            )
    return executed, errors


def _apply_watchlist_changes(
    conn: sqlite3.Connection,
    changes: list[WatchlistChange],
    user_id: str,
) -> tuple[list[dict], list[str]]:
    """Apply each watchlist add/remove; collect successes and error strings."""
    applied: list[dict] = []
    errors: list[str] = []
    for change in changes:
        ticker = change.ticker.upper().strip()
        try:
            if change.action == "add":
                wl.add_ticker(conn, ticker, user_id)
            else:
                wl.remove_ticker(conn, ticker, user_id)
            applied.append({"ticker": ticker, "action": change.action})
        except wl.WatchlistError as exc:
            errors.append(f"Watchlist change failed ({change.action} {ticker}): {exc}")
    return applied, errors


def _store_messages(
    conn: sqlite3.Connection,
    user_message: str,
    assistant_message: str,
    actions: dict,
    user_id: str,
) -> None:
    """Append the user turn and the assistant turn to ``chat_messages``."""
    now = _utc_now_iso()
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, "user", user_message, None, now),
    )
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            user_id,
            "assistant",
            assistant_message,
            json.dumps(actions),
            now,
        ),
    )
    conn.commit()


async def handle_chat(
    message: str,
    db_path: str,
    price_cache: PriceCache,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Run one chat turn: build context, call the LLM, execute actions, persist.

    Returns ``{message, trades_executed, watchlist_changes_applied, errors}``.
    """
    conn = get_db(db_path)
    try:
        portfolio_context = _build_portfolio_context(conn, price_cache, user_id)
        history = _load_history(conn, user_id)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": portfolio_context},
            *history,
            {"role": "user", "content": message},
        ]

        if _llm_mock_enabled():
            chat_response = MOCK_RESPONSE
        else:
            chat_response = _call_llm(messages)

        trades_executed, trade_errors = _apply_trades(
            conn, price_cache, chat_response.trades, user_id
        )
        watchlist_applied, watchlist_errors = _apply_watchlist_changes(
            conn, chat_response.watchlist_changes, user_id
        )
        errors = trade_errors + watchlist_errors

        actions = {
            "trades_executed": trades_executed,
            "watchlist_changes_applied": watchlist_applied,
            "errors": errors,
        }
        _store_messages(conn, message, chat_response.message, actions, user_id)

        return {
            "message": chat_response.message,
            "trades_executed": trades_executed,
            "watchlist_changes_applied": watchlist_applied,
            "errors": errors,
        }
    finally:
        conn.close()
