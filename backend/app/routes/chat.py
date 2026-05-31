"""Chat REST endpoints — POST /api/chat, GET /api/chat/history."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..db.schema import DEFAULT_USER_ID
from ..llm.chat import handle_chat
from ..market.cache import PriceCache
from ..state import AppState, get_cache, get_conn, get_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    content: Annotated[str, Field(min_length=1, max_length=2000)]


@router.post("")
async def chat(
    body: ChatRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
    state: AppState = Depends(get_state),
) -> dict:
    """POST /api/chat — send a message; returns {message, executed_actions}."""
    return await handle_chat(
        user_message=body.content,
        conn=conn,
        price_cache=cache,
        market_source=state.market_source,
    )


@router.get("/history")
async def get_chat_history(
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    """GET /api/chat/history — last 50 chat_messages ASC with parsed actions JSON."""
    rows = conn.execute(
        "SELECT id, role, content, actions, created_at FROM chat_messages "
        "WHERE user_id = ? ORDER BY created_at ASC LIMIT 50",
        (DEFAULT_USER_ID,),
    ).fetchall()

    result: list[dict] = []
    for r in rows:
        parsed_actions = json.loads(r["actions"]) if r["actions"] else None
        result.append(
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "actions": parsed_actions,
                "created_at": r["created_at"],
            }
        )
    return result
