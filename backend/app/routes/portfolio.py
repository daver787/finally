"""Portfolio API routes: view holdings, execute trades, fetch history."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.market.cache import PriceCache
from app.services import portfolio as pf
from app.state import get_cache, get_conn

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: Literal["buy", "sell"]

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be empty")
        return v

    @field_validator("quantity")
    @classmethod
    def _positive_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v


@router.get("")
async def get_portfolio(
    conn: sqlite3.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
) -> dict:
    """Return cash, positions, total value, and unrealized P&L."""
    return pf.get_portfolio(conn, cache)


@router.post("/trade")
async def execute_trade(
    body: TradeRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
) -> dict:
    """Execute a market order at the current price; return the updated portfolio.

    400 if validation fails (insufficient cash/shares, no price for the ticker).
    """
    try:
        trade = pf.execute_trade(conn, cache, body.ticker, body.quantity, body.side)
    except pf.TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    portfolio = pf.get_portfolio(conn, cache)
    portfolio["trade"] = trade
    return portfolio


@router.get("/history")
async def get_history(
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    """Return portfolio value snapshots over time (for the P&L chart)."""
    return pf.get_history(conn)
