"""Watchlist API routes.

Adding/removing a ticker also informs the market data source so the simulator
or Massive poller starts/stops producing prices for it.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.market.cache import PriceCache
from app.services import watchlist as wl
from app.state import AppState, get_cache, get_conn, get_state

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class AddTickerRequest(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be empty")
        return v


@router.get("")
async def list_watchlist(
    conn: sqlite3.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
) -> list[dict]:
    """Return watchlist tickers enriched with the latest cached prices."""
    return wl.get_watchlist(conn, cache)


@router.post("", status_code=201)
async def add_to_watchlist(
    body: AddTickerRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
    state: AppState = Depends(get_state),
) -> list[dict]:
    """Add a ticker to the watchlist; return the updated list. 400 if duplicate."""
    try:
        wl.add_ticker(conn, body.ticker)
    except wl.WatchlistError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if state.market_source is not None:
        await state.market_source.add_ticker(body.ticker)

    return wl.get_watchlist(conn, cache)


@router.delete("/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    conn: sqlite3.Connection = Depends(get_conn),
    cache: PriceCache = Depends(get_cache),
    state: AppState = Depends(get_state),
) -> list[dict]:
    """Remove a ticker from the watchlist; return the updated list. 404 if absent."""
    try:
        wl.remove_ticker(conn, ticker)
    except wl.TickerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if state.market_source is not None:
        await state.market_source.remove_ticker(ticker)

    return wl.get_watchlist(conn, cache)
