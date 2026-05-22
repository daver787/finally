"""Chat API route.

Wires ``POST /api/chat`` to the LLM chat handler, which builds portfolio
context, calls the LLM (or a mock), auto-executes any trades / watchlist
changes, and persists the exchange.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.llm import handle_chat
from app.market.cache import PriceCache
from app.state import AppState, get_cache, get_state

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(
    body: ChatRequest,
    state: AppState = Depends(get_state),
    cache: PriceCache = Depends(get_cache),
) -> dict:
    """Send a message to the AI assistant; return its reply and executed actions."""
    return await handle_chat(body.message, str(state.db_path), cache)
