"""Chat handler — builds portfolio context, calls LiteLLM (or mock),
auto-executes trades, persists conversation."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from ..db.schema import DEFAULT_USER_ID
from ..market.cache import PriceCache
from ..services.portfolio import (
    TradeError,
    build_portfolio_summary,
    execute_trade,
)
from ..services.watchlist import (
    WatchlistError,
)
from ..services.watchlist import (
    add_ticker as add_watchlist_ticker,
)
from ..services.watchlist import (
    remove_ticker as remove_watchlist_ticker,
)
from .schema import ChatResponse, TradeAction, WatchlistChange

logger = logging.getLogger(__name__)

# Cerebras-via-OpenRouter pinning — see .claude/skills/cerebras/SKILL.md.
MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

# Conversation context bound to keep prompt length predictable.
MAX_HISTORY = 100

SYSTEM_PROMPT = (
    "You are FinAlly, an AI trading assistant for a simulated $10k portfolio. "
    "Analyze the user's portfolio, suggest trades with reasoning, and execute "
    "trades when the user asks or agrees. Be concise and data-driven. Only "
    "trade tickers currently on the watchlist; to trade a new ticker, ADD it "
    "to the watchlist in the same response. Always respond with valid JSON "
    "matching the ChatResponse schema."
)

# Fixed mock response (PLAN.md §9). Used when LLM_MOCK=true to skip the
# OpenRouter call entirely so E2E tests / CI / dev have no external dependency.
MOCK_RESPONSE = ChatResponse(
    message=(
        "I've reviewed your portfolio. I'll pick up 1 share of AAPL to "
        "demonstrate trade execution."
    ),
    trades=[TradeAction(ticker="AAPL", side="buy", quantity=1)],
    watchlist_changes=[],
)


def _normalize_ticker(ticker: str) -> str:
    """Uppercase + strip a ticker symbol."""
    return ticker.upper().strip()


async def _apply_watchlist_changes(
    changes: list[WatchlistChange],
    conn: sqlite3.Connection,
    price_cache: PriceCache,
    market_source,
) -> None:
    """Apply watchlist add/remove operations BEFORE trades.

    Pitfall 6 ordering: if the LLM wants to add a ticker AND trade it in
    the same response, the watchlist add must run first so the market
    source can start streaming prices for the new ticker before the
    trade lookup runs. We swallow per-item errors (and log them) so one
    bad change never kills the whole response.
    """
    for change in changes:
        ticker = _normalize_ticker(change.ticker)
        try:
            if change.action == "add":
                try:
                    add_watchlist_ticker(ticker, conn=conn, price_cache=price_cache)
                except WatchlistError:
                    # Duplicate add is idempotent at the handler level.
                    pass
                await market_source.add_ticker(ticker)
            elif change.action == "remove":
                remove_watchlist_ticker(ticker, conn=conn)
                await market_source.remove_ticker(ticker)
        except Exception:
            logger.exception("Failed to apply watchlist change %r", change)


async def handle_chat(
    *,
    user_message: str,
    conn: sqlite3.Connection,
    price_cache: PriceCache,
    market_source,
) -> dict:
    """Handle one chat round-trip.

    Steps (mandatory ordering — see RESEARCH.md Pitfalls 6 and 10):

    1. Persist the user message.
    2. Build LLM context (portfolio summary + recent history).
    3. Call LiteLLM via Cerebras (or return the mock response).
    4. Apply ``watchlist_changes`` (Pitfall 6: BEFORE trades).
    5. Execute trades — success → ``executed_trades``, ``TradeError`` →
       ``errors``.
    6. Persist the assistant message with an ``actions`` JSON payload.
    7. Return ``{message, executed_actions}``.
    """
    # 1) User message first so the LLM's view of history is consistent.
    # All SQLite operations run in asyncio.to_thread so they never block the
    # event loop — same pattern as _snapshot_loop in main.py.
    now = datetime.now(timezone.utc).isoformat()
    msg_id = str(uuid.uuid4())

    def _insert_user() -> None:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, 'user', ?, NULL, ?)",
            (msg_id, DEFAULT_USER_ID, user_message, now),
        )
        conn.commit()

    await asyncio.to_thread(_insert_user)

    # 2) Build context for the LLM — portfolio summary + recent history.
    def _build_context() -> tuple[dict, list[dict]]:
        _summary = build_portfolio_summary(conn=conn, price_cache=price_cache)
        _rows = conn.execute(
            "SELECT role, content FROM chat_messages "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (DEFAULT_USER_ID, MAX_HISTORY),
        ).fetchall()
        _history = [{"role": r["role"], "content": r["content"]} for r in reversed(_rows)]
        return _summary, _history

    summary, history_msgs = await asyncio.to_thread(_build_context)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current portfolio: {json.dumps(summary)}"},
        *history_msgs,
    ]

    # 3) Mock branch — skip the network call entirely.
    if os.environ.get("LLM_MOCK", "false").lower() == "true":
        response = MOCK_RESPONSE
    else:
        # Imported lazily inside the try block so any import failure is
        # caught and surfaced as a graceful error message (not a 500).
        try:
            from litellm import acompletion
            raw = await acompletion(
                model=MODEL,
                messages=messages,
                response_format=ChatResponse,
                reasoning_effort="low",
                extra_body=EXTRA_BODY,
                timeout=30,
            )
            content = raw.choices[0].message.content
            response = ChatResponse.model_validate_json(content)
        except Exception as exc:  # noqa: BLE001 — graceful degrade for any LLM failure
            if isinstance(exc, TimeoutError) or "timeout" in str(exc).lower():
                logger.warning("LLM call timed out: %s", exc)
                response = ChatResponse(
                    message="I'm taking too long to respond, please try again.",
                    trades=[],
                    watchlist_changes=[],
                )
            else:
                logger.warning("LLM returned unparseable response: %s", exc)
                response = ChatResponse(
                    message=(
                        "I had trouble formatting my response, please try again."
                    ),
                    trades=[],
                    watchlist_changes=[],
                )

    # 4) Apply watchlist changes FIRST so newly-added tickers can be traded
    #    in the same response (Pitfall 6).
    await _apply_watchlist_changes(
        response.watchlist_changes, conn, price_cache, market_source
    )

    # 5) Execute trades in a thread — successes → executed_trades, TradeError → errors.
    _trades_to_run = list(response.trades)

    def _run_trades() -> tuple[list[dict], list[dict]]:
        _executed: list[dict] = []
        _errors: list[dict] = []
        for trade in _trades_to_run:
            try:
                result = execute_trade(
                    ticker=_normalize_ticker(trade.ticker),
                    side=trade.side,
                    quantity=trade.quantity,
                    conn=conn,
                    price_cache=price_cache,
                )
                _executed.append(result)
            except TradeError as exc:
                _errors.append(
                    {
                        "ticker": trade.ticker,
                        "side": trade.side,
                        "quantity": trade.quantity,
                        "error": str(exc),
                    }
                )
        return _executed, _errors

    executed_trades, errors = await asyncio.to_thread(_run_trades)

    # 6) Persist assistant message in a thread.
    actions_payload = {
        "trades": executed_trades,
        "errors": errors,
        "watchlist_changes": [c.model_dump() for c in response.watchlist_changes],
    }
    now2 = datetime.now(timezone.utc).isoformat()
    _resp_msg = response.message
    _actions_json = json.dumps(actions_payload)

    def _insert_assistant() -> None:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, 'assistant', ?, ?, ?)",
            (str(uuid.uuid4()), DEFAULT_USER_ID, _resp_msg, _actions_json, now2),
        )
        conn.commit()

    await asyncio.to_thread(_insert_assistant)

    logger.info(
        "Chat handled: trades=%d errors=%d watchlist=%d",
        len(executed_trades),
        len(errors),
        len(response.watchlist_changes),
    )
    return {"message": response.message, "executed_actions": actions_payload}
