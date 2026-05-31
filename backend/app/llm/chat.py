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
    "to the watchlist in the same response.\n\n"
    "You MUST reply with a SINGLE JSON object using EXACTLY these top-level "
    "field names:\n"
    "{\n"
    '  "message": "<your conversational reply to the user>",\n'
    '  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],\n'
    '  "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]\n'
    "}\n"
    'The "message" field is REQUIRED and must be a string containing your full '
    'reply. Use empty arrays [] for "trades" and "watchlist_changes" when there '
    "are none. Do NOT use any other top-level key names (no \"response\", "
    '"reply", "thoughts", "answer", etc.). You may use Markdown (bold, bullet '
    'lists, tables) inside the "message" string to format your reply.'
)

# The structured-output model (gpt-oss-120b via Cerebras) is not strictly
# constrained to our schema and occasionally wraps its reply under a different
# top-level key (e.g. {"response": ...} or {"thoughts": ..., "answer": ...}).
# When that happens we still want to surface the real reply rather than the
# canned "trouble formatting" fallback, so tolerant parsing maps any of these
# alias keys onto the required `message` field.
_MESSAGE_ALIASES = ("message", "response", "reply", "answer", "text", "content", "thoughts")

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


def _coerce_chat_response(content: str) -> ChatResponse:
    """Parse LLM content into a ChatResponse, tolerating field-name drift.

    The model usually returns the exact schema, in which case strict
    validation succeeds immediately. When it drifts (wrong top-level key for
    the reply, or malformed trades/watchlist arrays) we recover the real reply
    instead of discarding it:

    1. Strict ``ChatResponse.model_validate_json`` — the happy path.
    2. ``json.loads`` + remap any ``_MESSAGE_ALIASES`` key onto ``message``,
       defaulting ``trades`` / ``watchlist_changes`` to empty lists, then
       re-validate (so well-formed actions are still honored).
    3. If only the actions are malformed, keep the message and drop the
       actions rather than failing the whole turn.

    Raises if the content is not JSON / has no usable reply text — the caller
    turns that into the user-facing "trouble formatting" fallback.
    """
    try:
        return ChatResponse.model_validate_json(content)
    except Exception:
        pass

    data = json.loads(content)  # may raise json.JSONDecodeError -> caller fallback

    # A bare JSON string is itself a usable reply.
    if isinstance(data, str):
        if data.strip():
            return ChatResponse(message=data.strip(), trades=[], watchlist_changes=[])
        raise ValueError("empty LLM reply string")

    if not isinstance(data, dict):
        raise ValueError(f"LLM reply was not a JSON object (got {type(data).__name__})")

    message = next(
        (
            data[key].strip()
            for key in _MESSAGE_ALIASES
            if isinstance(data.get(key), str) and data[key].strip()
        ),
        None,
    )
    if message is None:
        raise ValueError("no usable message field in LLM reply")

    trades = data.get("trades")
    watchlist = data.get("watchlist_changes")
    if watchlist is None:
        watchlist = data.get("watchlist_update")  # observed drift alias
    normalized = {
        "message": message,
        "trades": trades if isinstance(trades, list) else [],
        "watchlist_changes": watchlist if isinstance(watchlist, list) else [],
    }
    try:
        return ChatResponse.model_validate(normalized)
    except Exception:
        # Reply text is good but the action arrays are malformed — keep the
        # reply, drop the actions (better than failing the whole response).
        return ChatResponse(message=message, trades=[], watchlist_changes=[])


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
        # caught and surfaced as a graceful error message (not a 500). The
        # network call and the response parsing are handled separately so a
        # transient API error and a schema-drift parse failure produce
        # distinct, accurate fallbacks.
        content: str | None = None
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
        except Exception as exc:  # noqa: BLE001 — graceful degrade for any LLM failure
            if isinstance(exc, TimeoutError) or "timeout" in str(exc).lower():
                logger.warning("LLM call timed out: %s", exc)
                response = ChatResponse(
                    message="I'm taking too long to respond, please try again.",
                    trades=[],
                    watchlist_changes=[],
                )
            else:
                logger.warning("LLM call failed: %s", exc)
                response = ChatResponse(
                    message=(
                        "I had trouble reaching the AI service, please try again."
                    ),
                    trades=[],
                    watchlist_changes=[],
                )

        if content is not None:
            try:
                response = _coerce_chat_response(content)
            except Exception as exc:  # noqa: BLE001 — last-resort parse fallback
                logger.warning(
                    "LLM returned unparseable response: %s; raw=%r",
                    exc,
                    content[:500] if isinstance(content, str) else content,
                )
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
