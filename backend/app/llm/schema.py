"""Pydantic structured-output schema for the FinAlly chat handler."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TradeAction(BaseModel):
    """A trade the LLM wants to execute."""

    ticker: str
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)


class WatchlistChange(BaseModel):
    """A watchlist add or remove the LLM wants to apply."""

    ticker: str
    action: str = Field(pattern="^(add|remove)$")


class ChatResponse(BaseModel):
    """The full structured response from the LLM."""

    message: str
    trades: list[TradeAction] = []
    watchlist_changes: list[WatchlistChange] = []
