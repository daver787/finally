"""Pydantic schema for the LLM structured-output response.

The LLM is required to return JSON matching :class:`ChatResponse`. The same
models are reused by tests and by the chat handler when parsing responses.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TradeAction(BaseModel):
    """A single trade the LLM wants to auto-execute."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistChange(BaseModel):
    """A single watchlist add/remove the LLM wants to apply."""

    ticker: str
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    """Structured response the LLM must produce for every chat turn."""

    message: str
    trades: list[TradeAction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)
